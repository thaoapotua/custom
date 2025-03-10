// #include "deepstream_app.h"
// #include "deepstream_config_file_parser.h"
// #include "nvds_version.h"
// #include <string.h>
// #include <unistd.h>
// #include <termios.h>
// #include <X11/Xlib.h>
// #include <X11/Xutil.h>
// #include <gst/gst.h>
// #include <sys/time.h>
// #include <stdio.h>
// #include <stdlib.h>
// #include <fcntl.h>
// #include <poll.h>

// #define MAX_INSTANCES 128
// #define APP_TITLE "DeepStream"
// #define FIFO_FILE_DET "/tmp/ds_detection_pipe"
// #define FIFO_FILE_SEG "/tmp/ds_segmentation_pipe"
// #define MAX_RETRIES 3
// #define RETRY_DELAY_MS 100
// #define WRITE_TIMEOUT_MS 1000

// typedef struct {
//     int fd;
//     const char* name;
//     struct pollfd pfd;
// } PipeInfo;

// static PipeInfo pipe_det = {-1, "Detection", {0}};
// static PipeInfo pipe_seg = {-1, "Segmentation", {0}};
// static gboolean ipc_initialized = FALSE;
// static GMutex pipe_mutex;
// static GCond pipe_cond;

// AppCtx *appCtx[MAX_INSTANCES];
// static guint cintr = FALSE;
// static GMainLoop *main_loop = NULL;
// static gboolean show_bbox_text = FALSE;
// static gboolean quit = FALSE;
// static gint return_value = 0;
// static guint num_instances;

// GST_DEBUG_CATEGORY (NVDS_APP);

// static gboolean write_to_pipe_with_timeout(PipeInfo *pipe, const char* data, size_t len) {
//     g_mutex_lock(&pipe_mutex);
    
//     pipe->pfd.fd = pipe->fd;
//     pipe->pfd.events = POLLOUT;
    
//     int ret = poll(&pipe->pfd, 1, WRITE_TIMEOUT_MS);
//     if (ret <= 0) {
//         g_print("Poll timeout or error on %s pipe\n", pipe->name);
//         g_mutex_unlock(&pipe_mutex);
//         return FALSE;
//     }

//     if (pipe->pfd.revents & POLLOUT) {
//         ssize_t written = write(pipe->fd, data, len);
//         g_mutex_unlock(&pipe_mutex);
//         if (written == len) {
//             g_print("Successfully wrote %zd bytes to %s pipe\n", written, pipe->name);
//             return TRUE;
//         } else {
//             g_print("Partial write to %s pipe: %zd/%zu bytes\n", 
//                 pipe->name, written, len);
//             return FALSE;
//         }
//     }

//     g_print("Pipe %s not ready for writing\n", pipe->name);
//     g_mutex_unlock(&pipe_mutex);
//     return FALSE;
// }

// static gboolean write_with_retry(PipeInfo *pipe, const char* data) {
//     int retry_count = 0;
//     gboolean success = FALSE;
    
//     while (retry_count < MAX_RETRIES && !success) {
//         success = write_to_pipe_with_timeout(pipe, data, strlen(data));
//         if (!success) {
//             retry_count++;
//             if (retry_count < MAX_RETRIES) {
//                 g_usleep(RETRY_DELAY_MS * 1000);
//             }
//         }
//     }
    
//     return success;
// }

// static void cleanup_pipes(void) {
//     g_mutex_lock(&pipe_mutex);
    
//     if (pipe_det.fd != -1) {
//         close(pipe_det.fd);
//         pipe_det.fd = -1;
//     }
//     if (pipe_seg.fd != -1) {
//         close(pipe_seg.fd);
//         pipe_seg.fd = -1;
//     }
    
//     unlink(FIFO_FILE_DET);
//     unlink(FIFO_FILE_SEG);
    
//     ipc_initialized = FALSE;
    
//     g_mutex_unlock(&pipe_mutex);
//     g_cond_broadcast(&pipe_cond);
// }

// static gboolean setup_pipes(void) {
//     g_mutex_lock(&pipe_mutex);

//     g_print("Opening detection pipe for writing...\n");
//     pipe_det.fd = open(FIFO_FILE_DET, O_WRONLY | O_NONBLOCK);
//     if (pipe_det.fd == -1) {
//         g_print("Failed to open detection pipe: %s\n", strerror(errno));
//         g_mutex_unlock(&pipe_mutex);
//         return FALSE;
//     }

//     g_print("Opening segmentation pipe for writing...\n");
//     pipe_seg.fd = open(FIFO_FILE_SEG, O_WRONLY | O_NONBLOCK);
//     if (pipe_seg.fd == -1) {
//         g_print("Failed to open segmentation pipe: %s\n", strerror(errno));
//         close(pipe_det.fd);
//         pipe_det.fd = -1;
//         g_mutex_unlock(&pipe_mutex);
//         return FALSE;
//     }

//     g_print("Both pipes opened successfully\n");
//     ipc_initialized = TRUE;
//     g_mutex_unlock(&pipe_mutex);
    
//     return TRUE;
// }

// static void all_bbox_generated(AppCtx * appCtx, GstBuffer * buf,
//     NvDsBatchMeta * batch_meta, guint index) 
// {
//     static GMutex print_lock;
//     static guint frame_count = 0;
    
//     g_mutex_lock(&print_lock);

//     g_print("Processing frame %u\n", frame_count++);

//     if (!batch_meta || !batch_meta->frame_meta_list || !ipc_initialized) {
//         g_print("No metadata or IPC not initialized\n");
//         g_mutex_unlock(&print_lock);
//         return;
//     }

//     guint stream_index = appCtx->index;
//     g_print("Processing Stream[%d]\n", stream_index);

//     for (NvDsMetaList * l_frame = batch_meta->frame_meta_list; l_frame != NULL;
//         l_frame = l_frame->next) {
//         NvDsFrameMeta *frame_meta = l_frame->data;
        
//         if (!frame_meta->obj_meta_list) {
//             g_print("No objects in frame %d\n", frame_meta->frame_num);
//             continue;
//         }

//         for (NvDsMetaList * l_obj = frame_meta->obj_meta_list; l_obj != NULL;
//             l_obj = l_obj->next) {
//             NvDsObjectMeta *obj = (NvDsObjectMeta *) l_obj->data;
            
//             char buffer[1024];
//             if (stream_index == 0) {
//                 snprintf(buffer, sizeof(buffer), 
//                     "{\"stream\":0,\"frame\":%d,\"class\":%d,\"confidence\":%.2f,"
//                     "\"bbox\":{\"x\":%.1f,\"y\":%.1f,\"w\":%.1f,\"h\":%.1f}}\n",
//                     frame_meta->frame_num,
//                     obj->class_id,
//                     obj->confidence,
//                     obj->rect_params.left,
//                     obj->rect_params.top,
//                     obj->rect_params.width,
//                     obj->rect_params.height);
                
//                 if (write_with_retry(&pipe_det, buffer)) {
//                     g_print("Sent detection data for frame %d\n", frame_meta->frame_num);
//                 } else {
//                     g_print("Failed to write detection data\n");
//                 }
                
//             } else {
//                 snprintf(buffer, sizeof(buffer),
//                     "{\"stream\":1,\"frame\":%d,\"track_id\":%lu,\"class\":%d,"
//                     "\"confidence\":%.2f,\"bbox\":{\"x\":%.1f,\"y\":%.1f,\"w\":%.1f,\"h\":%.1f}}\n",
//                     frame_meta->frame_num,
//                     obj->object_id,
//                     obj->class_id,
//                     obj->confidence,
//                     obj->rect_params.left,
//                     obj->rect_params.top,
//                     obj->rect_params.width,
//                     obj->rect_params.height);
                
//                 if (write_with_retry(&pipe_seg, buffer)) {
//                     g_print("Sent segmentation data for frame %d\n", frame_meta->frame_num);
//                 } else {
//                     g_print("Failed to write segmentation data\n");
//                 }
//             }
//         }
//     }

//     g_mutex_unlock(&print_lock);
// }

// static void _intr_handler(int signum) {
//     struct sigaction action;
//     g_print("User Interrupted..\n");
//     cintr = TRUE;
// }

// static gboolean check_for_interrupt(gpointer data) {
//     if (quit) {
//         return FALSE;
//     }

//     if (cintr) {
//         cintr = FALSE;
//         quit = TRUE;
//         cleanup_pipes();
//         g_main_loop_quit(main_loop);
//         return FALSE;
//     }
//     return TRUE;
// }

// static void _intr_setup(void) {
//     struct sigaction action;
//     memset(&action, 0, sizeof(action));
//     action.sa_handler = _intr_handler;
//     sigaction(SIGINT, &action, NULL);
// }

// int main(int argc, char *argv[]) {
//     GError *error = NULL;
//     guint i;

//     gst_init(&argc, &argv);
//     GST_DEBUG_CATEGORY_INIT(NVDS_APP, "NVDS_APP", 0, NULL);

//     num_instances = 2;
    
//     g_print("Setting up IPC pipes...\n");
//     if (!setup_pipes()) {
//         g_print("Failed to setup IPC pipes\n");
//         return -1;
//     }
    
//     g_print("Initializing config files...\n");
//     gchar **cfg_files = g_malloc0(sizeof(gchar *) * num_instances);
//     if (!cfg_files) {
//         cleanup_pipes();
//         return -1;
//     }

//     cfg_files[0] = g_strdup("/home/tat/deepstream-custom-app/configs/deepstream_app_config_box_wedcam.txt");
//     cfg_files[1] = g_strdup("/home/tat/deepstream-custom-app/configs/deepstream_app_config_seg.txt");

//     for (i = 0; i < num_instances; i++) {
//         appCtx[i] = g_malloc0(sizeof(AppCtx));
//         if (!appCtx[i]) {
//             g_print("Failed to allocate AppCtx for instance %d\n", i);
//             goto done;
//         }

//         appCtx[i]->person_class_id = -1;
//         appCtx[i]->car_class_id = -1;
//         appCtx[i]->index = i;
//         appCtx[i]->active_source_index = -1;
//         if (show_bbox_text) {
//             appCtx[i]->show_bbox_text = TRUE;
//         }

//         g_print("Parsing config file for Stream[%d]: %s\n", i, cfg_files[i]);
//         if (!parse_config_file(&appCtx[i]->config, cfg_files[i])) {
//             g_print("Failed to parse config file '%s'\n", cfg_files[i]);
//             goto done;
//         }

//         if (i == 0) {
//             appCtx[i]->config.tiled_display_config.rows = 1;
//             appCtx[i]->config.tiled_display_config.columns = 1;
//             appCtx[i]->config.tiled_display_config.width = 960;
//             appCtx[i]->config.tiled_display_config.height = 540;
//             appCtx[i]->config.sink_bin_sub_bin_config[0].render_config.offset_x = 0;
//             appCtx[i]->config.sink_bin_sub_bin_config[0].render_config.offset_y = 0;
//         } else {
//             appCtx[i]->config.tiled_display_config.rows = 1;
//             appCtx[i]->config.tiled_display_config.columns = 1;
//             appCtx[i]->config.tiled_display_config.width = 960;
//             appCtx[i]->config.tiled_display_config.height = 540;
//             appCtx[i]->config.sink_bin_sub_bin_config[0].render_config.offset_x = 960;
//             appCtx[i]->config.sink_bin_sub_bin_config[0].render_config.offset_y = 0;
//         }
//     }

//     g_print("Creating pipelines...\n");
//     for (i = 0; i < num_instances; i++) {
//         g_print("Creating pipeline for Stream[%d]\n", i);
        
//         if (!create_pipeline(appCtx[i], NULL, all_bbox_generated, NULL, NULL)) {
//             g_print("Failed to create pipeline for Stream[%d]\n", i);
//             goto done;
//         }
//     }

//     main_loop = g_main_loop_new(NULL, FALSE);
//     _intr_setup();
//     g_timeout_add(400, check_for_interrupt, NULL);

//     g_print("Setting pipelines to PLAYING state...\n");
//     for (i = 0; i < num_instances; i++) {
//         GstStateChangeReturn ret = gst_element_set_state(appCtx[i]->pipeline.pipeline,
//                 GST_STATE_PLAYING);
                
//         if (ret == GST_STATE_CHANGE_FAILURE) {
//             g_print("Failed to set pipeline %d to PLAYING\n", i);
//             goto done;
//         }
//         g_print("Pipeline %d is PLAYING\n", i);
//     }

//     g_print("Running main loop...\n");
//     g_main_loop_run(main_loop);

// done:
//     g_print("Cleaning up...\n");

//     for (i = 0; i < num_instances; i++) {
//         if (appCtx[i]) {
//             if (appCtx[i]->pipeline.pipeline) {
//                 gst_element_set_state(appCtx[i]->pipeline.pipeline, GST_STATE_NULL);
//             }
//             destroy_pipeline(appCtx[i]);
//             g_free(appCtx[i]);
//         }
//         if (cfg_files && cfg_files[i]) {
//             g_free(cfg_files[i]);
//         }
//     }
    
//     if (cfg_files)
//         g_free(cfg_files);
        
//     cleanup_pipes();
//     g_mutex_clear(&pipe_mutex);
//     g_cond_clear(&pipe_cond);
    
//     if (main_loop)
//         g_main_loop_unref(main_loop);
        
//     g_print("Application %s\n", return_value == 0 ? "completed successfully" : "failed");
    
//     gst_deinit();
//     return return_value;
// }
