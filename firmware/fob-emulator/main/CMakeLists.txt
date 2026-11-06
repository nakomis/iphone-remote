# protocol.c is the real fob's, so the emulator can't drift from the firmware.
idf_component_register(SRCS "main.c" "../../fob/src/protocol.c"
                       INCLUDE_DIRS "../../fob/src"
                       PRIV_REQUIRES bt esp_driver_gpio esp_driver_usb_serial_jtag esp_timer nvs_flash vfs)
