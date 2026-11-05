cmake_minimum_required(VERSION 3.20.0)

# The fob's own board (boards/nakomis/iphone_remote_fob) and devicetree binding.
list(APPEND BOARD_ROOT ${CMAKE_CURRENT_SOURCE_DIR})
list(APPEND DTS_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(iphone_remote_fob)

target_sources(app PRIVATE src/main.c src/protocol.c)
