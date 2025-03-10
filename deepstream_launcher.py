#!/usr/bin/env python3
import os
import json
import time
import signal
import logging
import threading
import select
import fcntl
import subprocess
from datetime import datetime
from queue import Queue, Empty
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class PipeConfig:
    path: str
    fd: Optional[int] = None
    reader_thread: Optional[threading.Thread] = None

class DeepStreamLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(
            log_dir, 
            f'deepstream_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

class StreamProcessor:
    def __init__(self):
        self.logger = DeepStreamLogger("StreamProcessor")
        self.detection_results = []
        self.segmentation_results = []

    def process_stream_data(self, data: Dict[str, Any]):
        try:
            stream_id = data.get('stream')
            
            if stream_id == 0:
                self._process_detection(data)
            elif stream_id == 1:
                self._process_segmentation(data)
            else:
                self.logger.logger.warning(f"Unknown stream ID: {stream_id}")
                
        except Exception as e:
            self.logger.logger.error(f"Error processing stream data: {e}")

    def _process_detection(self, data: Dict[str, Any]):
        frame = data.get('frame', -1)
        class_id = data.get('class', -1)
        confidence = data.get('confidence', 0)
        bbox = data.get('bbox', {})
        
        result = {
            'frame': frame,
            'class_id': class_id,
            'confidence': confidence,
            'bbox': bbox,
            'timestamp': time.time()
        }
        
        self.detection_results.append(result)
        if len(self.detection_results) > 1000:
            self.detection_results = self.detection_results[-1000:]
            
        self.logger.logger.info(
            f"\nDetection (Stream 0) | Frame {frame}:"
            f"\n- Class ID: {class_id}"
            f"\n- Confidence: {confidence:.2f}"
            f"\n- BBox: x={bbox.get('x', 0):.1f}, y={bbox.get('y', 0):.1f}, "
            f"w={bbox.get('w', 0):.1f}, h={bbox.get('h', 0):.1f}"
        )

    def _process_segmentation(self, data: Dict[str, Any]):
        frame = data.get('frame', -1)
        track_id = data.get('track_id', -1)
        class_id = data.get('class', -1)
        confidence = data.get('confidence', 0)
        bbox = data.get('bbox', {})
        
        result = {
            'frame': frame,
            'track_id': track_id,
            'class_id': class_id,
            'confidence': confidence,
            'bbox': bbox,
            'timestamp': time.time()
        }
        
        self.segmentation_results.append(result)
        if len(self.segmentation_results) > 1000:
            self.segmentation_results = self.segmentation_results[-1000:]
            
        self.logger.logger.info(
            f"\nSegmentation (Stream 1) | Frame {frame}:"
            f"\n- Track ID: {track_id}"
            f"\n- Class ID: {class_id}"
            f"\n- Confidence: {confidence:.2f}"
            f"\n- BBox: x={bbox.get('x', 0):.1f}, y={bbox.get('y', 0):.1f}, "
            f"w={bbox.get('w', 0):.1f}, h={bbox.get('h', 0):.1f}"
        )

    def get_statistics(self):
        stats = {
            "detection": {
                "total_frames": len(set(r['frame'] for r in self.detection_results)),
                "total_objects": len(self.detection_results),
                "classes": {},
                "avg_confidence": 0
            },
            "segmentation": {
                "total_frames": len(set(r['frame'] for r in self.segmentation_results)),
                "total_objects": len(self.segmentation_results),
                "unique_tracks": len(set(r['track_id'] for r in self.segmentation_results)),
                "classes": {},
                "avg_confidence": 0
            }
        }
        
        if self.detection_results:
            stats["detection"]["avg_confidence"] = sum(r['confidence'] for r in self.detection_results) / len(self.detection_results)
            for r in self.detection_results:
                class_id = r['class_id']
                stats["detection"]["classes"][class_id] = stats["detection"]["classes"].get(class_id, 0) + 1
                
        if self.segmentation_results:
            stats["segmentation"]["avg_confidence"] = sum(r['confidence'] for r in self.segmentation_results) / len(self.segmentation_results)
            for r in self.segmentation_results:
                class_id = r['class_id']
                stats["segmentation"]["classes"][class_id] = stats["segmentation"]["classes"].get(class_id, 0) + 1
                
        return stats

class DeepStreamLauncher:
    def __init__(self, deepstream_path: str = "./deepstream-app"):
        self.logger = DeepStreamLogger("DeepStreamLauncher")
        self.deepstream_path = os.path.abspath(deepstream_path)
        
        self.detection_pipe = PipeConfig("/tmp/ds_detection_pipe")
        self.segmentation_pipe = PipeConfig("/tmp/ds_segmentation_pipe")
        
        self.det_queue = Queue()
        self.seg_queue = Queue()
        
        self.process = None
        self.running = True
        self.initialized = False
        
        self.stream_processor = StreamProcessor()
        
        self.pipe_lock = threading.Lock()
        self.process_lock = threading.Lock()
        self.shutdown_event = threading.Event()

    def cleanup_pipes(self):
        with self.pipe_lock:
            for pipe in [self.detection_pipe, self.segmentation_pipe]:
                if pipe.fd is not None:
                    try:
                        os.close(pipe.fd)
                        pipe.fd = None
                    except OSError as e:
                        self.logger.logger.error(f"Error closing {pipe.path}: {e}")
                        
                if os.path.exists(pipe.path):
                    try:
                        os.unlink(pipe.path)
                    except OSError as e:
                        self.logger.logger.error(f"Error removing {pipe.path}: {e}")

    def create_pipes(self) -> bool:
        try:
            self.cleanup_pipes()
            
            for pipe in [self.detection_pipe, self.segmentation_pipe]:
                os.mkfifo(pipe.path, 0o666)
                self.logger.logger.info(f"Created pipe: {pipe.path}")

            time.sleep(0.1)
            return True
        except Exception as e:
            self.logger.logger.error(f"Error creating pipes: {e}")
            self.cleanup_pipes()
            return False

    def open_pipes(self) -> bool:
        try:
            with self.pipe_lock:
                self.logger.logger.info("Opening pipes for reading...")
                
                for pipe in [self.detection_pipe, self.segmentation_pipe]:
                    pipe.fd = os.open(pipe.path, os.O_RDONLY | os.O_NONBLOCK)
                    flags = fcntl.fcntl(pipe.fd, fcntl.F_GETFL)
                    fcntl.fcntl(pipe.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                    self.logger.logger.info(f"Opened pipe: {pipe.path}")
                
                return True
        except Exception as e:
            self.logger.logger.error(f"Error opening pipes: {e}")
            self.cleanup_pipes()
            return False

    def read_from_pipe(self, pipe: PipeConfig, queue: Queue, buffer_size: int = 4096):
        self.logger.logger.info(f"Starting reader for {pipe.path}")
        buffer = ""
        consecutive_errors = 0
        last_log_time = time.time()
        
        while not self.shutdown_event.is_set():
            try:
                ready = select.select([pipe.fd], [], [], 0.1)[0]
                current_time = time.time()
                
                if current_time - last_log_time > 5:
                    self.logger.logger.debug(f"Reader for {pipe.path} waiting for data...")
                    last_log_time = current_time
                    
                if ready:
                    data = os.read(pipe.fd, buffer_size)
                    if data:
                        self.logger.logger.debug(f"Raw data received on {pipe.path}: {data}")
                        buffer += data.decode()
                        consecutive_errors = 0
                        last_log_time = current_time
                        
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            try:
                                parsed_data = json.loads(line)
                                self.logger.logger.debug(
                                    f"Parsed data from {pipe.path}:\n{json.dumps(parsed_data, indent=2)}"
                                )
                                queue.put(parsed_data)
                            except json.JSONDecodeError as e:
                                self.logger.logger.error(
                                    f"JSON parse error on {pipe.path}: {e}\nRaw line: {line}"
                                )
                else:
                    time.sleep(0.01)
                    
            except Exception as e:
                if not self.shutdown_event.is_set():
                    consecutive_errors += 1
                    if consecutive_errors >= 10:
                        self.logger.logger.error(
                            f"Multiple errors reading from {pipe.path}: {e}"
                        )
                        consecutive_errors = 0
                    time.sleep(0.1)

    def start_deepstream(self):
        try:
            if not os.path.exists(self.deepstream_path):
                self.logger.logger.error(f"DeepStream executable not found at: {self.deepstream_path}")
                return False

            env = os.environ.copy()
            env.update({
                "GST_DEBUG": "3",
                "GST_DEBUG_DUMP_DOT_DIR": "/tmp",
                "NVDS_ENABLE_STDOUT": "1"
            })
            
            self.logger.logger.info("Starting DeepStream...")
            self.process = subprocess.Popen(
                [self.deepstream_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                env=env
            )
            
            self.logger.logger.info(f"DeepStream process PID: {self.process.pid}")
            
            def monitor_output(pipe, name):
                while True:
                    line = pipe.readline()
                    if not line:
                        break
                    self.logger.logger.info(f"DeepStream {name}: {line.strip()}")
                    
            threading.Thread(
                target=monitor_output,
                args=(self.process.stdout, "STDOUT"),
                daemon=True
            ).start()
            
            threading.Thread(
                target=monitor_output,
                args=(self.process.stderr, "STDERR"),
                daemon=True
            ).start()

            time.sleep(2)
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                self.logger.logger.error(f"DeepStream failed to start: {stderr}")
                return False

            def check_process():
                while self.running:
                    if self.process.poll() is not None:
                        self.logger.logger.error("DeepStream process terminated unexpectedly")
                        self.stop()
                        break
                    time.sleep(1)
                    
            threading.Thread(target=check_process, daemon=True).start()

            self.logger.logger.info("DeepStream started successfully")
            return True
                
        except Exception as e:
            self.logger.logger.error(f"Error starting DeepStream: {e}")
            return False

    def process_queues(self):
        while not self.shutdown_event.is_set():
            try:
                # Process both queues
                for queue in [self.det_queue, self.seg_queue]:
                    try:
                        data = queue.get_nowait()
                        self.stream_processor.process_stream_data(data)
                    except Empty:
                        pass

                # Print statistics every 10 seconds
                if time.time() % 10 < 0.1:
                    stats = self.stream_processor.get_statistics()
                    self.logger.logger.info("\nStream Statistics:")
                    self.logger.logger.info(json.dumps(stats, indent=2))

                time.sleep(0.01)
            except Exception as e:
                self.logger.logger.error(f"Error processing queues: {e}")
                time.sleep(0.1)

    def start(self):
        try:
            self.logger.logger.info("Starting DeepStream Launcher...")
            
            if not self.create_pipes():
                self.logger.logger.error("Failed to create pipes")
                return False

            if not self.open_pipes():
                self.logger.logger.error("Failed to open pipes")
                return False

            if not self.start_deepstream():
                self.logger.logger.error("Failed to start DeepStream")
                self.stop()
                return False

            for pipe, queue in [
                (self.detection_pipe, self.det_queue),
                (self.segmentation_pipe, self.seg_queue)
            ]:
                pipe.reader_thread = threading.Thread(
                    target=self.read_from_pipe,
                    args=(pipe, queue),
                    daemon=True
                )
                pipe.reader_thread.start()

            threading.Thread(
                target=self.process_queues,
                daemon=True
            ).start()

            self.logger.logger.info("DeepStream Launcher started successfully")
            return True

        except Exception as e:
            self.logger.logger.error(f"Error starting DeepStream Launcher: {e}")
            self.stop()
            return False

    def stop(self):
            self.logger.logger.info("Stopping DeepStream Launcher...")
            self.running = False
            self.shutdown_event.set()
            
            if self.process:
                self.logger.logger.info("Terminating DeepStream process...")
                try:
                    # Try graceful shutdown first
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.logger.logger.warning("Force killing DeepStream process...")
                        self.process.kill()
                        self.process.wait()
                except Exception as e:
                    self.logger.logger.error(f"Error stopping DeepStream: {e}")
                finally:
                    self.process = None
            
            # Wait for threads to finish
            time.sleep(0.5)
            
            self.cleanup_pipes()
            self.logger.logger.info("DeepStream Launcher stopped")

def main():
    launcher = DeepStreamLauncher()
    try:
        if launcher.start():
            print("System running. Press Ctrl+C to stop.")
            while launcher.running:
                try:
                    time.sleep(0.1)
                    if launcher.process and launcher.process.poll() is not None:
                        print("\nDeepStream process terminated unexpectedly")
                        break
                except KeyboardInterrupt:
                    print("\nStopping system...")
                    break
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        launcher.stop()

if __name__ == "__main__":
    main()