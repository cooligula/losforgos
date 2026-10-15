# libgiftranscode: the GIF resizer that Messaging uses to fit animated GIFs into an MMS.
# Upstream builds it with Soong against the platform's giflib (external/giflib), which the
# `deps` of apps.toml fetch into libs/giflib. Plain malloc/free throughout, so nothing here
# interferes with hardware memory tagging.
cmake_minimum_required(VERSION 3.18.1)
project(giftranscode C CXX)

set(GIFLIB ${CMAKE_CURRENT_SOURCE_DIR}/libs/giflib)

add_library(gif STATIC
    ${GIFLIB}/dgif_lib.c
    ${GIFLIB}/egif_lib.c
    ${GIFLIB}/gifalloc.c
    ${GIFLIB}/gif_err.c
    ${GIFLIB}/gif_hash.c
    ${GIFLIB}/quantize.c
    ${GIFLIB}/openbsd-reallocarray.c)
target_include_directories(gif PUBLIC ${GIFLIB})
# Same flags as the Android.bp of giflib: its reallocarray() must not collide with bionic's.
target_compile_options(gif PRIVATE
    -Wno-format -Wno-sign-compare -Wno-unused-parameter
    -Dreallocarray=bionic_reallocarray "SHELL:-include malloc.h" -Ureallocarray)

add_library(giftranscode SHARED jni/GifTranscoder.cpp)
target_compile_options(giftranscode PRIVATE -Wno-unused-parameter -Wno-switch)
target_link_libraries(giftranscode gif log dl)
# 16 KB pages (Android 15+ devices that use them).
target_link_options(giftranscode PRIVATE -Wl,-z,max-page-size=16384)
