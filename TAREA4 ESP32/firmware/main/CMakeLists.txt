idf_component_register(SRCS "main.c" "wifi_header.c" "wifi_metadata.c" INCLUDE_DIRS "." REQUIRES esp_wifi esp_event esp_netif bt nvs_flash json driver esp_timer)
