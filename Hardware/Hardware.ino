#include <driver/i2s.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <stdint.h>
#include <stdbool.h>
#include <Adafruit_NeoPixel.h>

#define I2S_WS 12
#define I2S_SD 13
#define I2S_SCK 11
#define I2S_PORT I2S_NUM_0
#define I2S_SAMPLE_RATE   (16000)
#define I2S_SAMPLE_BITS   (16)
#define I2S_READ_LEN      (4 * 1024)
#define RECORD_TIME (6)
#define I2S_CHANNEL_NUM   (1)
#define FLASH_RECORD_SIZE (I2S_CHANNEL_NUM * I2S_SAMPLE_RATE * I2S_SAMPLE_BITS / 8 * RECORD_TIME)
bool streaming = false;
WebSocketsClient ws;
bool socketConnected=false;
char i2s_read_buff[I2S_READ_LEN];
uint8_t write_buff[I2S_READ_LEN];
Adafruit_NeoPixel rgb(1, 18, NEO_GRB + NEO_KHZ800);

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  rgb.begin();
  rgb.clear();
  i2sInit();
  InitWifi();
  InitSocket();
  int i2s_read_len = I2S_READ_LEN;
  size_t bytes_read;
  i2s_read(I2S_PORT, (void*) i2s_read_buff, i2s_read_len, &bytes_read, portMAX_DELAY);
  i2s_read(I2S_PORT, (void*) i2s_read_buff, i2s_read_len, &bytes_read, portMAX_DELAY);
  Serial.println(" *** Recording Start *** ");

}

void loop() {
  // put your main code here, to run repeatedly:
  ws.loop(); 
  int i2s_read_len = I2S_READ_LEN;
  size_t bytes_read;

  //read data from I2S bus, in this case, from ADC.
  i2s_read(I2S_PORT, (void*) i2s_read_buff, i2s_read_len, &bytes_read, portMAX_DELAY);
  i2s_adc_data_scale(write_buff, (uint8_t*)i2s_read_buff, i2s_read_len);
  bool valid=true;
  if(valid && socketConnected){
      if(!streaming){
        ws.sendTXT("START");
        streaming=true;
      }
    ws.sendBIN(write_buff, bytes_read);
  }
  else if(streaming && socketConnected){
    ws.sendTXT("END");
    streaming = false;
  }
}
void i2sInit(){
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = I2S_SAMPLE_RATE,
    .bits_per_sample = i2s_bits_per_sample_t(I2S_SAMPLE_BITS),
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = 1
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);

  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_set_pin(I2S_PORT, &pin_config);
}

void i2s_adc_data_scale(uint8_t * d_buff, uint8_t* s_buff, uint32_t len)
{
    uint32_t j = 0;
    uint32_t dac_value = 0;
    for (int i = 0; i < len; i += 2) {
        dac_value = ((((uint16_t) (s_buff[i + 1] & 0xf) << 8) | ((s_buff[i + 0]))));
        d_buff[j++] = 0;
        d_buff[j++] = dac_value * 256 / 2048;
    }
}
void InitWifi(){
  char* ssid = "HONOR Magic6 Lite 5G";
  char* password = "301b0cefba66";

  WiFi.begin(ssid, password);
  while(WiFi.status() != WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

}
void wsEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("[WS] Disconnected");
            socketConnected=false;
            InitSocket();
            break;

        case WStype_CONNECTED:
            Serial.println("[WS] Connected to server");
            socketConnected=true;
            streaming=false;
            break;

        case WStype_TEXT:
            Serial.printf("[WS] Text: %s\n", payload);
            break;

        case WStype_BIN:
            Serial.printf("[WS] Binary data received, length: %u\n", length);
            if(length==3){
              rgb.setPixelColor(0,(uint8_t)payload[0],(uint8_t)payload[1],(uint8_t)payload[2]);
              rgb.show();
            }
            break;

        case WStype_ERROR:
            Serial.println("[WS] Error");
            break;

        case WStype_PING:
            Serial.println("[WS] Ping received");
            break;

        case WStype_PONG:
            Serial.println("[WS] Pong received");
            break;
    }
}
void InitSocket(){
  ws.begin("10.58.58.130", 8888, "/audio");
  ws.onEvent(wsEvent);
  ws.setReconnectInterval(5000);
}