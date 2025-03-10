# CUDA_VER?=
# ifeq ($(CUDA_VER),)
#   $(error "CUDA_VER is not set")
# endif

# APP := deepstream-app
# NVDS_VERSION := 6.2

# DS_ROOT := /opt/nvidia/deepstream/deepstream-$(NVDS_VERSION)

# CC := gcc
# CXX := g++

# # Include paths
# INCLUDES := -I./ \
#            -I./includes \
#            -I./common \
#            -I./yaml \
#            -I$(DS_ROOT)/sources/apps/apps-common/includes \
#            -I$(DS_ROOT)/sources/includes \
#            -I/usr/local/cuda-$(CUDA_VER)/include

# # Libraries
# LIBS := -L$(DS_ROOT)/lib \
#         -L/usr/local/cuda-$(CUDA_VER)/lib64 \
#         -lnvdsgst_meta \
#         -lnvds_meta \
#         -lnvdsgst_helper \
#         -lnvdsgst_customhelper \
#         -lnvdsgst_smartrecord \
#         -lnvds_utils \
#         -lnvds_msgbroker \
#         -lyaml-cpp \
#         -lcudart \
#         -lcuda \
#         -lgstrtspserver-1.0 \
#         -lstdc++

# # Compiler flags
# CFLAGS := -DDS_VERSION_MINOR=1 \
#           -DDS_VERSION_MAJOR=5 \
#           -fPIC

# # Add pkg-config
# PKG_CONFIG := gstreamer-1.0 gstreamer-video-1.0 x11 json-glib-1.0
# CFLAGS += $(shell pkg-config --cflags $(PKG_CONFIG))
# LIBS += $(shell pkg-config --libs $(PKG_CONFIG))

# # Source files
# SRCS := deepstream_app.c \
#         deepstream_app_config_parser.c \
#         deepstream_app_main.c \
#         $(wildcard common/*.c)

# CPP_SRCS := deepstream_app_config_parser_yaml.cpp \
#             $(wildcard yaml/*.cpp)

# # Generate object file names
# OBJS := $(SRCS:%.c=%.o) $(CPP_SRCS:%.cpp=%.o)

# .PHONY: all clean

# all: $(APP)

# %.o: %.c
# 	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# %.o: %.cpp
# 	$(CXX) $(CFLAGS) $(INCLUDES) -c $< -o $@

# $(APP): $(OBJS)
# 	$(CXX) -o $@ $(OBJS) $(LIBS) -Wl,-rpath,$(DS_ROOT)/lib

# clean:
# 	rm -f $(APP) $(OBJS)
# 	rm -f common/*.o yaml/*.o

CUDA_VER?=
ifeq ($(CUDA_VER),)
  $(error "CUDA_VER is not set")
endif

APP := deepstream-app
NVDS_VERSION := 6.2

DS_ROOT := /opt/nvidia/deepstream/deepstream-$(NVDS_VERSION)

CC := gcc
CXX := g++

INCLUDES := -I./ \
           -I./includes \
           -I./common \
           -I./yaml \
           -I$(DS_ROOT)/sources/apps/apps-common/includes \
           -I$(DS_ROOT)/sources/includes \
           -I/usr/local/cuda-$(CUDA_VER)/include \
           -I/usr/include/json-glib-1.0 \
           -I/usr/include/glib-2.0 \
           -I/usr/lib/x86_64-linux-gnu/glib-2.0/include

LIBS := -L$(DS_ROOT)/lib \
        -L/usr/local/cuda-$(CUDA_VER)/lib64 \
        -lnvdsgst_meta \
        -lnvds_meta \
        -lnvdsgst_helper \
        -lnvdsgst_customhelper \
        -lnvdsgst_smartrecord \
        -lnvds_utils \
        -lnvds_msgbroker \
        -lyaml-cpp \
        -lcudart \
        -lcuda \
        -lgstrtspserver-1.0 \
        -lstdc++ \
        -ljson-glib-1.0 \
        -lgobject-2.0 \
        -lglib-2.0

CFLAGS := -DDS_VERSION_MINOR=1 \
          -DDS_VERSION_MAJOR=5 \
          -fPIC \
          -Wall \
          -Wno-deprecated-declarations \
          -g \
          -O2

PKG_CONFIG := gstreamer-1.0 gstreamer-video-1.0 x11 json-glib-1.0
CFLAGS += $(shell pkg-config --cflags $(PKG_CONFIG))
LIBS += $(shell pkg-config --libs $(PKG_CONFIG))

SRCS := deepstream_app.c \
        deepstream_app_config_parser.c \
        deepstream_app_main.c \
        $(wildcard common/*.c)

CPP_SRCS := deepstream_app_config_parser_yaml.cpp \
            $(wildcard yaml/*.cpp)

OBJS := $(SRCS:%.c=%.o) $(CPP_SRCS:%.cpp=%.o)

.PHONY: all clean

all: $(APP)

%.o: %.c
	@echo "Compiling $<..."
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

%.o: %.cpp
	@echo "Compiling $<..."
	$(CXX) $(CFLAGS) $(INCLUDES) -c $< -o $@

$(APP): $(OBJS)
	@echo "Linking $@..."
	$(CXX) -o $@ $(OBJS) $(LIBS) -Wl,-rpath,$(DS_ROOT)/lib
	@echo "Build complete!"

clean:
	@echo "Cleaning..."
	rm -f $(APP) $(OBJS)
	rm -f common/*.o yaml/*.o
	@echo "Clean complete!"

run: $(APP)
	@echo "Running $(APP)..."
	./$(APP)

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  all        - Build the application (default)"
	@echo "  clean      - Remove built files"
	@echo "  run        - Build and run the application"
	@echo "  help       - Show this help message"
	@echo ""
	@echo "Variables:"
	@echo "  CUDA_VER   - CUDA version (required)"
	@echo ""
	@echo "Example usage:"
	@echo "  make CUDA_VER=11.4"
	@echo "  make clean"
	@echo "  make run CUDA_VER=11.4"