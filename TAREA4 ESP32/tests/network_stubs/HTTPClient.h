#pragma once
inline int httpCalls=0,httpCode=200;
inline String sentPayload;
struct HTTPClient{void setConnectTimeout(int){}void setTimeout(int){}void setReuse(bool){}bool begin(WiFiClientSecure&,const String&){return true;}void addHeader(const char*,const char*){}int POST(uint8_t*p,size_t n){httpCalls++;sentPayload=std::string(reinterpret_cast<char*>(p),n);return httpCode;}void end(){}};
