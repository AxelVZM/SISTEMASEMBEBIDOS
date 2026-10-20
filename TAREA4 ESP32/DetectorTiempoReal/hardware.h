#pragma once
uint8_t oledAddress=0;bool oledReady=false,rtcPresent=false;uint32_t hardwareAt=0,probeAt=0;
uint8_t oledBuffer[1024]{};
bool clockValid(){time_t t=time(nullptr);return t>=1704067200LL&&t<4102444800LL;}
bool i2cWrite(uint8_t addr,const uint8_t *data,size_t n){Wire.beginTransmission(addr);Wire.write(data,n);return Wire.endTransmission()==0;}
bool i2cRead(uint8_t addr,uint8_t reg,uint8_t *out,size_t n){Wire.beginTransmission(addr);Wire.write(reg);if(Wire.endTransmission(false)!=0)return false;if(Wire.requestFrom(addr,uint8_t(n))!=n){while(Wire.available())Wire.read();return false;}for(size_t i=0;i<n;i++)out[i]=Wire.read();return true;}
uint8_t bcd(uint8_t n){return (n/10)*16+n%10;}int fromBcd(uint8_t n){return (n>>4)*10+(n&15);}
bool rtcLoad(){
 uint8_t data[7],status;if(!i2cRead(0x68,0,data,7)||!i2cRead(0x68,0x0f,&status,1)||(status&0x80)||(data[5]&0x80))return false;
 tm date{};date.tm_sec=fromBcd(data[0]&0x7f);date.tm_min=fromBcd(data[1]&0x7f);if(data[2]&0x40){int h=fromBcd(data[2]&0x1f);if(h<1||h>12)return false;date.tm_hour=h%12+((data[2]&0x20)?12:0);}else date.tm_hour=fromBcd(data[2]&0x3f);
 date.tm_mday=fromBcd(data[4]&0x3f);date.tm_mon=fromBcd(data[5]&0x1f)-1;date.tm_year=fromBcd(data[6])+100;
 if(date.tm_sec>59||date.tm_min>59||date.tm_hour>23||date.tm_mday<1||date.tm_mday>31||date.tm_mon<0||date.tm_mon>11||date.tm_year<124)return false;
 tm original=date;time_t epoch=mktime(&date);tm check{};gmtime_r(&epoch,&check);if(check.tm_mday!=original.tm_mday||check.tm_mon!=original.tm_mon||check.tm_year!=original.tm_year)return false;timeval t{epoch,0};return settimeofday(&t,nullptr)==0;
}
bool syncClock(uint32_t epoch){
 if(epoch<1704067200u||epoch>=4102444800u)return false;timeval tv{time_t(epoch),0};if(settimeofday(&tv,nullptr)!=0)return false;
 if(rtcPresent){time_t t=epoch;tm date{};gmtime_r(&t,&date);uint8_t data[]={0,bcd(date.tm_sec),bcd(date.tm_min),bcd(date.tm_hour),bcd(date.tm_wday+1),bcd(date.tm_mday),bcd(date.tm_mon+1),bcd(date.tm_year-100)};if(!i2cWrite(0x68,data,sizeof(data)))return false;uint8_t status;if(!i2cRead(0x68,0x0f,&status,1))return false;uint8_t clear[]={0x0f,uint8_t(status&0x7f)};return i2cWrite(0x68,clear,2);}return true;
}
struct Glyph {char ch;uint8_t cols[5];};
const Glyph font[]={
 {'0',{0x3e,0x51,0x49,0x45,0x3e}},{'1',{0,0x42,0x7f,0x40,0}},{'2',{0x42,0x61,0x51,0x49,0x46}},{'3',{0x21,0x41,0x45,0x4b,0x31}},{'4',{0x18,0x14,0x12,0x7f,0x10}},{'5',{0x27,0x45,0x45,0x45,0x39}},{'6',{0x3c,0x4a,0x49,0x49,0x30}},{'7',{1,0x71,9,5,3}},{'8',{0x36,0x49,0x49,0x49,0x36}},{'9',{6,0x49,0x49,0x29,0x1e}},
 {'A',{0x7e,0x11,0x11,0x11,0x7e}},{'B',{0x7f,0x49,0x49,0x49,0x36}},{'C',{0x3e,0x41,0x41,0x41,0x22}},{'D',{0x7f,0x41,0x41,0x22,0x1c}},{'E',{0x7f,0x49,0x49,0x49,0x41}},{'F',{0x7f,9,9,9,1}},{'G',{0x3e,0x41,0x49,0x49,0x7a}},{'H',{0x7f,8,8,8,0x7f}},{'I',{0,0x41,0x7f,0x41,0}},{'J',{0x20,0x40,0x41,0x3f,1}},{'K',{0x7f,8,0x14,0x22,0x41}},{'L',{0x7f,0x40,0x40,0x40,0x40}},{'M',{0x7f,2,0xc,2,0x7f}},{'N',{0x7f,4,8,0x10,0x7f}},{'O',{0x3e,0x41,0x41,0x41,0x3e}},{'P',{0x7f,9,9,9,6}},{'Q',{0x3e,0x41,0x51,0x21,0x5e}},{'R',{0x7f,9,0x19,0x29,0x46}},{'S',{0x46,0x49,0x49,0x49,0x31}},{'T',{1,1,0x7f,1,1}},{'U',{0x3f,0x40,0x40,0x40,0x3f}},{'V',{0x1f,0x20,0x40,0x20,0x1f}},{'W',{0x3f,0x40,0x38,0x40,0x3f}},{'X',{0x63,0x14,8,0x14,0x63}},{'Y',{7,8,0x70,8,7}},{'Z',{0x61,0x51,0x49,0x45,0x43}},{':',{0,0x36,0x36,0,0}},{'-',{8,8,8,8,8}},{'/',{0x20,0x10,8,4,2}},{' ',{0,0,0,0,0}}};
void drawText(int x,int y,const String &s,int scale=1){for(size_t k=0;k<s.length();k++){const uint8_t *g=nullptr;for(auto &item:font)if(item.ch==s[k])g=item.cols;if(g)for(int a=0;a<5;a++)for(int b=0;b<7;b++)if(g[a]&(1<<b))for(int dx=0;dx<scale;dx++)for(int dy=0;dy<scale;dy++){int px=x+a*scale+dx,py=y+b*scale+dy;if(px>=0&&px<128&&py>=0&&py<64)oledBuffer[px+(py/8)*128]|=1<<(py%8);}x+=6*scale;if(x>=128)break;}}
bool oledCommand(const uint8_t *commands,size_t n){uint8_t data[32];if(n>31)return false;data[0]=0;memcpy(data+1,commands,n);return i2cWrite(oledAddress,data,n+1);}
void probeHardware(){
 if(ENABLE_RTC){uint8_t status;rtcPresent=i2cRead(0x68,0x0f,&status,1);}
 if(!ENABLE_OLED||oledReady)return;
 for(uint8_t addr:{uint8_t(0x3c),uint8_t(0x3d)}){Wire.beginTransmission(addr);if(Wire.endTransmission()!=0)continue;oledAddress=addr;const uint8_t init[]={0xae,0xd5,0x80,0xa8,0x3f,0xd3,0,0x40,0x8d,0x14,0x20,0,0xa1,0xc8,0xda,0x12,0x81,0x7f,0xd9,0xf1,0xdb,0x40,0xa4,0xa6,0xaf};if(oledCommand(init,sizeof(init))){oledReady=true;break;}}
}
void initializeHardware(){setenv("TZ","UTC0",1);tzset();if(LED_PIN>=0){pinMode(LED_PIN,OUTPUT);digitalWrite(LED_PIN,!LED_ACTIVE_HIGH);}Wire.begin(I2C_SDA,I2C_SCL,400000);Wire.setTimeOut(10);probeHardware();if(rtcPresent)rtcLoad();}
void hardwareTick(uint32_t now){
 auto c=counts(now);bool fault=!radioReady||bleFailed||!fsReady;uint32_t phase=now%1500;bool on=fault?(phase<100||(phase>=200&&phase<300)||(phase>=400&&phase<500)):(c.wifiCapacity||c.bleCapacity)?(phase<100||(phase>=250&&phase<350)):phase<60;
 if(LED_PIN>=0)digitalWrite(LED_PIN,on?LED_ACTIVE_HIGH:!LED_ACTIVE_HIGH);
 if(now-probeAt>=30000){probeAt=now;probeHardware();if(rtcPresent&&!clockValid())rtcLoad();}
 if(now-hardwareAt<1000||!oledReady)return;hardwareAt=now;memset(oledBuffer,0,sizeof(oledBuffer));drawText(0,0,"SENSOR V71-60S");drawText(0,18,"WIFI");drawText(45,13,String(c.wifi),2);drawText(0,40,"BLE");drawText(45,35,String(c.ble),2);
 String footer=blePhase?"RADIO BLE":String("WIFI CANAL ")+String(channel);if(networkBusy())footer="RED - PAUSA RADIO";else if(fault)footer="REVISAR ESTADO";else if(c.wifiCapacity||c.bleCapacity)footer="TABLA AL LIMITE";else if(clockValid()&&(now/5000)%2){time_t epoch=time(nullptr);tm d{};gmtime_r(&epoch,&d);char text[20];snprintf(text,sizeof(text),"UTC %02d:%02d:%02d",d.tm_hour,d.tm_min,d.tm_sec);footer=text;}drawText(0,56,footer);
 const uint8_t window[]={0x21,0,127,0x22,0,7};if(!oledCommand(window,sizeof(window))){oledReady=false;return;}for(size_t at=0;at<1024;at+=16){uint8_t packet[17];packet[0]=0x40;memcpy(packet+1,oledBuffer+at,16);if(!i2cWrite(oledAddress,packet,sizeof(packet))){oledReady=false;break;}}
}
