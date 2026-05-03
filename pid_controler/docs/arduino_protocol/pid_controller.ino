/**
 * pid_controller.ino - PID控制上位机通信协议 Arduino版
 * 适配"模仿者小队"直流减速电机闭环控制上位机
 * 波特率:115200  编码器:A=2,B=3  PWM:5  方向:6
 */
#include <Arduino.h>

#define F1 0xAA
#define F2 0x55
#define F3 0x55
#define F4 0xAA
#define CMD_PID   0x01
#define CMD_TARGET 0x02
#define CMD_MODE   0x03
#define CMD_START  0x04
#define CMD_REPORT 0x81
#define PPR 1000

struct PidP {float kp,ki,kd;};
struct Cmd {float target;uint8_t mode,start;};

PidP po={1,0.1,0.01},pi_={2,0.5,0};
Cmd cmd={0,0,0};
volatile long enc=0;
float inte=0,pe=0;
enum PS{S0,S1,S2,S3,S4,S5,S6,S7};
PS st=S0;
uint8_t rb[128],dl,cm,di,cs;

float b2f(uint8_t*b){float f;memcpy(&f,b,4);return f;}
void f2b(float f,uint8_t*b){memcpy(b,&f,4);}

void parse(uint8_t b){
  switch(st){
  case S0:if(b==F1)st=S1;break;
  case S1:st=(b==F2)?S2:S0;break;
  case S2:dl=b;cs=b;st=S3;break;
  case S3:cm=b;cs^=b;di=0;st=(dl>4)?S4:S5;break;
  case S4:rb[di++]=b;cs^=b;if(di>=dl-4)st=S5;break;
  case S5:st=(b==(cs&0xFF))?S6:S0;break;
  case S6:st=(b==F3)?S7:S0;break;
  case S7:
    if(b==F4){switch(cm){
      case CMD_PID:if(dl>=17){uint8_t l=rb[0];PidP&p=(l==0)?po:pi_;
        p.kp=b2f(rb+1);p.ki=b2f(rb+5);p.kd=b2f(rb+9);}break;
      case CMD_TARGET:cmd.target=b2f(rb);break;
      case CMD_MODE:cmd.mode=rb[0];break;
      case CMD_START:cmd.start=rb[0];break;}}
    st=S0;break;
  }
}

void report(float m,float o,float s,float f){
  uint8_t fr[32],d[16];uint8_t i=0,c=0;
  f2b(m,d);f2b(o,d+4);f2b(s,d+8);f2b(f,d+12);
  fr[i++]=F1;fr[i++]=F2;fr[i++]=20;c^=20;
  fr[i++]=CMD_REPORT;c^=CMD_REPORT;
  for(int j=0;j<16;j++){fr[i++]=d[j];c^=d[j];}
  fr[i++]=c&0xFF;fr[i++]=F3;fr[i++]=F4;
  Serial.write(fr,i);
}

void encISR(){if(digitalRead(3))enc++;else enc--;}

float pid(float sp,float m,PidP&p,float dt){
  float e=sp-m;inte+=e*dt;inte=constrain(inte,-50.f,50.f);
  float d=(e-pe)/dt;pe=e;
  return constrain(p.kp*e+p.ki*inte+p.kd*d,-255.f,255.f);
}

void setup(){
  Serial.begin(115200);
  pinMode(2,INPUT_PULLUP);pinMode(3,INPUT_PULLUP);
  pinMode(5,OUTPUT);pinMode(6,OUTPUT);
  attachInterrupt(digitalPinToInterrupt(2),encISR,RISING);
}

void loop(){
  static uint32_t lt=0;
  uint32_t n=millis();float dt=(n-lt)/1000.f;
  if(dt<0.01)return;lt=n;
  while(Serial.available())parse(Serial.read());
  if(cmd.start){
    long c=enc;enc=0;
    float sr=(float)c/PPR*60.f/dt,pd=(float)c/PPR*360.f;
    float o=0,m=0;
    switch(cmd.mode){
    case 0:m=sr;o=pid(cmd.target,sr,po,dt);break;
    case 1:m=pd;o=pid(cmd.target,pd,po,dt);break;
    case 3:{float s=pid(cmd.target,pd,po,dt);m=sr;o=pid(s,sr,pi_,dt);}break;
    }
    int pw=constrain((int)o,-255,255);
    digitalWrite(6,pw>=0?HIGH:LOW);analogWrite(5,abs(pw));
    report(m,o,cmd.target,m);
  }else analogWrite(5,0);
}