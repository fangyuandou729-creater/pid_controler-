# MCU端通信协议与示例代码

## 通信协议说明

### 协议格式
```
[帧头 0xAA 0x55] [长度 1B] [命令 1B] [数据 NB] [XOR校验 1B] [帧尾 0x55 0xAA]
```

### 帧结构
| 字段 | 长度 | 说明 |
|------|------|------|
| 帧头 | 2B | 固定 `0xAA 0x55` |
| 长度 | 1B | 数据区长度 + 4（cmd + data + checksum + padding） |
| 命令 | 1B | 命令类型 |
| 数据 | NB | 变长数据 |
| 校验 | 1B | XOR校验（长度 ^ 命令 ^ 数据[0] ^ 数据[1] ^ ...） |
| 帧尾 | 2B | 固定 `0x55 0xAA` |

### 命令类型

| 命令 | 方向 | 说明 | 数据格式 |
|------|------|------|----------|
| 0x01 | PC→MCU | 设置PID参数 | `[loop_id:u8][kp:f32][ki:f32][kd:f32]` (13字节) |
| 0x02 | PC→MCU | 设置目标值 | `[target:f32]` (4字节) |
| 0x03 | PC→MCU | 设置控制模式 | `[mode:u8]` (1字节) |
| 0x04 | PC→MCU | 启停控制 | `[start:u8]` (1字节, 1=启动, 0=停止) |
| 0x05 | PC→MCU | 查询状态 | 无数据 |
| 0x81 | MCU→PC | 数据上报 | `[measurement:f32][output:f32][setpoint:f32][feedback:f32]` (16字节) |

### 数据类型
- `u8`: 无符号8位整数
- `f32`: 32位浮点数（小端序，IEEE 754）

---

## STM32 HAL 示例代码

### protocol.h

```c
#ifndef __PROTOCOL_H
#define __PROTOCOL_H

#include "main.h"
#include <stdint.h>
#include <string.h>

/* 帧头帧尾 */
#define FRAME_HEADER_1  0xAA
#define FRAME_HEADER_2  0x55
#define FRAME_TAIL_1    0x55
#define FRAME_TAIL_2    0xAA

/* 命令类型 */
#define CMD_SET_PID_PARAMS  0x01
#define CMD_SET_TARGET      0x02
#define CMD_SET_MODE        0x03
#define CMD_START_STOP      0x04
#define CMD_QUERY_STATUS    0x05
#define CMD_DATA_REPORT     0x81

/* 控制模式 */
#define MODE_SPEED      0
#define MODE_POSITION   1
#define MODE_ANGLE      2
#define MODE_CASCADE    3

/* 接收缓冲区大小 */
#define RX_BUF_SIZE     128

/* 帧解析状态机 */
typedef enum {
    STATE_IDLE,
    STATE_HEADER_2,
    STATE_LENGTH,
    STATE_CMD,
    STATE_DATA,
    STATE_CHECKSUM,
    STATE_TAIL_1,
    STATE_TAIL_2
} ParseState;

/* 接收到的PID参数 */
typedef struct {
    uint8_t loop_id;    // 0:单环/外环, 1:内环
    float kp;
    float ki;
    float kd;
} PidParams_t;

/* 接收到的控制指令 */
typedef struct {
    float target;           // 目标值
    uint8_t mode;           // 控制模式
    uint8_t start_stop;     // 启停
} ControlCmd_t;

/* 协议上下文 */
typedef struct {
    ParseState state;
    uint8_t rx_buf[RX_BUF_SIZE];
    uint8_t data_len;
    uint8_t cmd;
    uint8_t data_index;
    uint8_t checksum;
    uint8_t rx_byte;
} ProtocolCtx_t;

/* 全局变量声明 */
extern ProtocolCtx_t g_protocol;
extern PidParams_t g_pid_outer;
extern PidParams_t g_pid_inner;
extern ControlCmd_t g_ctrl_cmd;

/* 函数声明 */
void Protocol_Init(void);
void Protocol_ParseByte(uint8_t byte);
void Protocol_ProcessFrame(uint8_t cmd, uint8_t *data, uint8_t len);
float BytesToFloat(uint8_t *bytes);
void FloatToBytes(float val, uint8_t *bytes);

/* 发送数据上报帧 */
void Protocol_SendDataReport(float measurement, float output, float setpoint, float feedback);

#endif /* __PROTOCOL_H */
```

### protocol.c

```c
#include "protocol.h"
#include "usart.h"

/* 全局变量 */
ProtocolCtx_t g_protocol;
PidParams_t g_pid_outer = {1.0f, 0.1f, 0.01f};
PidParams_t g_pid_inner = {2.0f, 0.5f, 0.0f};
ControlCmd_t g_ctrl_cmd = {0, MODE_SPEED, 0};

/**
 * @brief 初始化协议
 */
void Protocol_Init(void)
{
    memset(&g_protocol, 0, sizeof(ProtocolCtx_t));
    g_protocol.state = STATE_IDLE;
}

/**
 * @brief 字节数组转float（小端序）
 */
float BytesToFloat(uint8_t *bytes)
{
    float val;
    memcpy(&val, bytes, 4);
    return val;
}

/**
 * @brief float转字节数组（小端序）
 */
void FloatToBytes(float val, uint8_t *bytes)
{
    memcpy(bytes, &val, 4);
}

/**
 * @brief 逐字节解析协议帧（在串口接收中断中调用）
 * @param byte 接收到的字节
 */
void Protocol_ParseByte(uint8_t byte)
{
    ProtocolCtx_t *ctx = &g_protocol;
    
    switch (ctx->state) {
    case STATE_IDLE:
        if (byte == FRAME_HEADER_1)
            ctx->state = STATE_HEADER_2;
        break;
        
    case STATE_HEADER_2:
        if (byte == FRAME_HEADER_2) {
            ctx->state = STATE_LENGTH;
            ctx->checksum = 0;
        } else {
            ctx->state = STATE_IDLE;
        }
        break;
        
    case STATE_LENGTH:
        ctx->data_len = byte;
        ctx->checksum ^= byte;
        ctx->state = STATE_CMD;
        break;
        
    case STATE_CMD:
        ctx->cmd = byte;
        ctx->checksum ^= byte;
        ctx->data_index = 0;
        if (ctx->data_len > 4) {
            ctx->state = STATE_DATA;
        } else {
            ctx->state = STATE_CHECKSUM;
        }
        break;
        
    case STATE_DATA:
        if (ctx->data_index < RX_BUF_SIZE) {
            ctx->rx_buf[ctx->data_index] = byte;
            ctx->checksum ^= byte;
            ctx->data_index++;
        }
        if (ctx->data_index >= (uint8_t)(ctx->data_len - 4)) {
            ctx->state = STATE_CHECKSUM;
        }
        break;
        
    case STATE_CHECKSUM:
        if (byte == (ctx->checksum & 0xFF)) {
            ctx->state = STATE_TAIL_1;
        } else {
            ctx->state = STATE_IDLE;  // 校验失败
        }
        break;
        
    case STATE_TAIL_1:
        if (byte == FRAME_TAIL_1) {
            ctx->state = STATE_TAIL_2;
        } else {
            ctx->state = STATE_IDLE;
        }
        break;
        
    case STATE_TAIL_2:
        if (byte == FRAME_TAIL_2) {
            // 帧完整，处理数据
            Protocol_ProcessFrame(ctx->cmd, ctx->rx_buf, ctx->data_len - 4);
        }
        ctx->state = STATE_IDLE;
        break;
        
    default:
        ctx->state = STATE_IDLE;
        break;
    }
}

/**
 * @brief 处理解析完成的帧
 */
void Protocol_ProcessFrame(uint8_t cmd, uint8_t *data, uint8_t len)
{
    switch (cmd) {
    case CMD_SET_PID_PARAMS:
        // data: [loop_id:u8][kp:f32][ki:f32][kd:f32]
        if (len >= 13) {
            uint8_t loop_id = data[0];
            float kp = BytesToFloat(&data[1]);
            float ki = BytesToFloat(&data[5]);
            float kd = BytesToFloat(&data[9]);
            
            if (loop_id == 0) {
                g_pid_outer.kp = kp;
                g_pid_outer.ki = ki;
                g_pid_outer.kd = kd;
            } else {
                g_pid_inner.kp = kp;
                g_pid_inner.ki = ki;
                g_pid_inner.kd = kd;
            }
        }
        break;
        
    case CMD_SET_TARGET:
        // data: [target:f32]
        if (len >= 4) {
            g_ctrl_cmd.target = BytesToFloat(data);
        }
        break;
        
    case CMD_SET_MODE:
        // data: [mode:u8]
        if (len >= 1) {
            g_ctrl_cmd.mode = data[0];
        }
        break;
        
    case CMD_START_STOP:
        // data: [start:u8]
        if (len >= 1) {
            g_ctrl_cmd.start_stop = data[0];
        }
        break;
        
    case CMD_QUERY_STATUS:
        // 可以在此处上报当前状态
        break;
        
    default:
        break;
    }
}

/**
 * @brief 发送数据上报帧到PC
 */
void Protocol_SendDataReport(float measurement, float output, float setpoint, float feedback)
{
    uint8_t frame[32];
    uint8_t checksum;
    uint8_t data[16];
    uint8_t idx = 0;
    
    // 数据打包
    FloatToBytes(measurement, &data[0]);
    FloatToBytes(output, &data[4]);
    FloatToBytes(setpoint, &data[8]);
    FloatToBytes(feedback, &data[12]);
    
    // 帧头
    frame[idx++] = FRAME_HEADER_1;
    frame[idx++] = FRAME_HEADER_2;
    
    // 长度 = 数据长度(16) + 4
    frame[idx++] = 20;
    checksum = 20;
    
    // 命令
    frame[idx++] = CMD_DATA_REPORT;
    checksum ^= CMD_DATA_REPORT;
    
    // 数据
    for (int i = 0; i < 16; i++) {
        frame[idx++] = data[i];
        checksum ^= data[i];
    }
    
    // 校验
    frame[idx++] = checksum & 0xFF;
    
    // 帧尾
    frame[idx++] = FRAME_TAIL_1;
    frame[idx++] = FRAME_TAIL_2;
    
    // 通过串口发送
    HAL_UART_Transmit(&huart1, frame, idx, 100);
}
```

---

## STM32 主循环示例（main.c片段）

```c
#include "protocol.h"

/* PID控制器结构体 */
typedef struct {
    float kp, ki, kd;
    float setpoint;
    float integral;
    float prev_error;
    float output_min, output_max;
} PID_Controller_t;

/* 初始化PID */
void PID_Init(PID_Controller_t *pid, float kp, float ki, float kd)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->setpoint = 0;
    pid->integral = 0;
    pid->prev_error = 0;
    pid->output_min = -100;
    pid->output_max = 100;
}

/* PID计算 */
float PID_Compute(PID_Controller_t *pid, float measurement, float dt)
{
    float error = pid->setpoint - measurement;
    
    // 比例
    float p_term = pid->kp * error;
    
    // 积分（带限幅）
    pid->integral += error * dt;
    if (pid->integral > 50.0f) pid->integral = 50.0f;
    if (pid->integral < -50.0f) pid->integral = -50.0f;
    float i_term = pid->ki * pid->integral;
    
    // 微分
    float d_term = pid->kd * (error - pid->prev_error) / dt;
    pid->prev_error = error;
    
    // 输出限幅
    float output = p_term + i_term + d_term;
    if (output > pid->output_max) output = pid->output_max;
    if (output < pid->output_min) output = pid->output_min;
    
    return output;
}

/* 全局变量 */
PID_Controller_t pid_speed;
PID_Controller_t pid_position;

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART1_UART_Init();
    MX_TIM1_Init();      // 编码器
    MX_TIM2_Init();      // PWM输出
    
    Protocol_Init();
    PID_Init(&pid_speed, 1.0f, 0.1f, 0.01f);
    PID_Init(&pid_position, 1.0f, 0.1f, 0.01f);
    
    // 启动串口接收中断
    uint8_t rx_byte;
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    
    uint32_t last_tick = HAL_GetTick();
    
    while (1) {
        uint32_t now = HAL_GetTick();
        float dt = (now - last_tick) / 1000.0f;
        last_tick = now;
        
        if (dt <= 0 || dt > 0.1f) continue;
        
        if (g_ctrl_cmd.start_stop) {
            // 读取编码器
            int32_t encoder_count = (int16_t)__HAL_TIM_GET_COUNTER(&htim1);
            float speed_rpm = (float)encoder_count * 60.0f / 1000.0f / dt;  // 假设1000线编码器
            float position_deg = (float)encoder_count * 360.0f / 1000.0f;
            
            // 同步PID参数
            pid_speed.kp = g_pid_outer.kp;
            pid_speed.ki = g_pid_outer.ki;
            pid_speed.kd = g_pid_outer.kd;
            
            // 根据模式选择
            float output = 0;
            float measurement = 0;
            
            switch (g_ctrl_cmd.mode) {
            case MODE_SPEED:
                pid_speed.setpoint = g_ctrl_cmd.target;
                measurement = speed_rpm;
                output = PID_Compute(&pid_speed, measurement, dt);
                break;
                
            case MODE_POSITION:
                pid_speed.setpoint = g_ctrl_cmd.target;
                measurement = position_deg;
                output = PID_Compute(&pid_speed, measurement, dt);
                break;
                
            case MODE_CASCADE:
                // 外环: 位置 -> 速度设定
                pid_position.kp = g_pid_outer.kp;
                pid_position.ki = g_pid_outer.ki;
                pid_position.kd = g_pid_outer.kd;
                pid_position.setpoint = g_ctrl_cmd.target;
                float speed_setpoint = PID_Compute(&pid_position, position_deg, dt);
                
                // 内环: 速度 -> PWM
                pid_speed.kp = g_pid_inner.kp;
                pid_speed.ki = g_pid_inner.ki;
                pid_speed.kd = g_pid_inner.kd;
                pid_speed.setpoint = speed_setpoint;
                output = PID_Compute(&pid_speed, speed_rpm, dt);
                measurement = speed_rpm;
                break;
            }
            
            // 设置电机PWM
            int16_t pwm = (int16_t)output;
            if (pwm >= 0) {
                HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_SET);   // 正转
                __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pwm);
            } else {
                HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_RESET); // 反转
                __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, -pwm);
            }
            
            // 上报数据到PC
            Protocol_SendDataReport(measurement, output, g_ctrl_cmd.target, measurement);
            
        } else {
            // 停止状态
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 0);
        }
        
        HAL_Delay(10);  // 100Hz控制周期
    }
}

/* 串口接收中断回调 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {
        Protocol_ParseByte(rx_byte);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);  // 重新启动接收
    }
}
```

---

## Arduino 示例代码

```cpp
#include <Arduino.h>

/* 协议定义 */
#define FRAME_HEADER_1  0xAA
#define FRAME_HEADER_2  0x55
#define FRAME_TAIL_1    0x55
#define FRAME_TAIL_2    0xAA
#define CMD_SET_PID_PARAMS  0x01
#define CMD_SET_TARGET      0x02
#define CMD_SET_MODE        0x03
#define CMD_START_STOP      0x04
#define CMD_DATA_REPORT     0x81

/* PID参数 */
struct PidParams {
    float kp, ki, kd;
};

/* 控制指令 */
struct ControlCmd {
    float target;
    uint8_t mode;
    uint8_t start_stop;
};

/* 全局变量 */
PidParams pid_outer = {1.0, 0.1, 0.01};
PidParams pid_inner = {2.0, 0.5, 0.0};
ControlCmd ctrl_cmd = {0, 0, 0};

/* 协议解析状态 */
enum ParseState { IDLE, HEADER2, LENGTH, CMD, DATA, CHECKSUM, TAIL1, TAIL2 };
ParseState state = IDLE;
uint8_t rx_buf[128];
uint8_t data_len, cmd, data_idx, checksum;

/* PID控制器 */
float pid_integral = 0, pid_prev_error = 0;

float bytesToFloat(uint8_t *b) {
    float f;
    memcpy(&f, b, 4);
    return f;
}

void floatToBytes(float f, uint8_t *b) {
    memcpy(b, &f, 4);
}

/* 解析一个字节 */
void parseByte(uint8_t byte) {
    switch (state) {
    case IDLE:
        if (byte == FRAME_HEADER_1) state = HEADER2;
        break;
    case HEADER2:
        state = (byte == FRAME_HEADER_2) ? LENGTH : IDLE;
        break;
    case LENGTH:
        data_len = byte;
        checksum = byte;
        state = CMD;
        break;
    case CMD:
        cmd = byte;
        checksum ^= byte;
        data_idx = 0;
        state = (data_len > 4) ? DATA : CHECKSUM;
        break;
    case DATA:
        rx_buf[data_idx++] = byte;
        checksum ^= byte;
        if (data_idx >= data_len - 4) state = CHECKSUM;
        break;
    case CHECKSUM:
        if (byte == (checksum & 0xFF)) state = TAIL1;
        else state = IDLE;
        break;
    case TAIL1:
        state = (byte == FRAME_TAIL_1) ? TAIL2 : IDLE;
        break;
    case TAIL2:
        if (byte == FRAME_TAIL_2) {
            // 处理帧
            switch (cmd) {
            case CMD_SET_PID_PARAMS:
                if (data_len >= 17) {
                    uint8_t loop_id = rx_buf[0];
                    if (loop_id == 0) {
                        pid_outer.kp = bytesToFloat(&rx_buf[1]);
                        pid_outer.ki = bytesToFloat(&rx_buf[5]);
                        pid_outer.kd = bytesToFloat(&rx_buf[9]);
                    } else {
                        pid_inner.kp = bytesToFloat(&rx_buf[1]);
                        pid_inner.ki = bytesToFloat(&rx_buf[5]);
                        pid_inner.kd = bytesToFloat(&rx_buf[9]);
                    }
                }
                break;
            case CMD_SET_TARGET:
                ctrl_cmd.target = bytesToFloat(rx_buf);
                break;
            case CMD_SET_MODE:
                ctrl_cmd.mode = rx_buf[0];
                break;
            case CMD_START_STOP:
                ctrl_cmd.start_stop = rx_buf[0];
                break;
            }
        }
        state = IDLE;
        break;
    }
}

/* 发送数据上报 */
void sendDataReport(float measurement, float output, float setpoint, float feedback) {
    uint8_t frame[32], data[16];
    uint8_t idx = 0, cs = 0;
    
    floatToBytes(measurement, &data[0]);
    floatToBytes(output, &data[4]);
    floatToBytes(setpoint, &data[8]);
    floatToBytes(feedback, &data[12]);
    
    frame[idx++] = FRAME_HEADER_1;
    frame[idx++] = FRAME_HEADER_2;
    frame[idx++] = 20; cs ^= 20;
    frame[idx++] = CMD_DATA_REPORT; cs ^= CMD_DATA_REPORT;
    for (int i = 0; i < 16; i++) {
        frame[idx++] = data[i];
        cs ^= data[i];
    }
    frame[idx++] = cs & 0xFF;
    frame[idx++] = FRAME_TAIL_1;
    frame[idx++] = FRAME_TAIL_2;
    
    Serial.write(frame, idx);
}

/* 简单PID */
float computePID(float setpoint, float measurement, PidParams &pid, float dt) {
    float error = setpoint - measurement;
    pid_integral += error * dt;
    pid_integral = constrain(pid_integral, -50.0f, 50.0f);
    float derivative = (error - pid_prev_error) / dt;
    pid_prev_error = error;
    float output = pid.kp * error + pid.ki * pid_integral + pid.kd * derivative;
    return constrain(output, -255.0f, 255.0f);
}

/* 编码器引脚 */
#define ENCODER_A 2
#define ENCODER_B 3
volatile long encoder_count = 0;

void encoderISR() {
    if (digitalRead(ENCODER_B)) encoder_count++;
    else encoder_count--;
}

void setup() {
    Serial.begin(115200);
    pinMode(ENCODER_A, INPUT);
    pinMode(ENCODER_B, INPUT);
    attachInterrupt(digitalPinToInterrupt(ENCODER_A), encoderISR, RISING);
    
    pinMode(5, OUTPUT);   // PWM
    pinMode(6, OUTPUT);   // 方向
}

void loop() {
    static uint32_t last_time = 0;
    uint32_t now = millis();
    float dt = (now - last_time) / 1000.0f;
    if (dt < 0.01) return;  // 100Hz
    last_time = now;
    
    // 接收串口数据
    while (Serial.available()) {
        parseByte(Serial.read());
    }
    
    if (ctrl_cmd.start_stop) {
        // 计算速度和位置
        long count = encoder_count;
        float speed_rpm = (count / 1000.0f) * 60.0f / dt;  // 假设1000线编码器
        float position_deg = (count / 1000.0f) * 360.0f;
        encoder_count = 0;
        
        float output = 0;
        float measurement = 0;
        
        switch (ctrl_cmd.mode) {
        case 0:  // 速度
            measurement = speed_rpm;
            output = computePID(ctrl_cmd.target, speed_rpm, pid_outer, dt);
            break;
        case 1:  // 位置
            measurement = position_deg;
            output = computePID(ctrl_cmd.target, position_deg, pid_outer, dt);
            break;
        }
        
        // 驱动电机
        int pwm = (int)output;
        if (pwm >= 0) {
            digitalWrite(6, HIGH);
            analogWrite(5, min(pwm, 255));
        } else {
            digitalWrite(6, LOW);
            analogWrite(5, min(-pwm, 255));
        }
        
        // 上报数据
        sendDataReport(measurement, output, ctrl_cmd.target, measurement);
    } else {
        analogWrite(5, 0);
    }
}
```

---

## 注意事项

1. **字节序**: 所有浮点数使用小端序（Little-Endian），与x86/ARM一致
2. **波特率**: 默认115200，8N1
3. **控制周期**: 建议10ms（100Hz），与上位机仿真频率一致
4. **编码器**: 示例假设1000线编码器，根据实际修改
5. **PWM**: 示例使用8位PWM（0-255），实际使用16位定时器时修改范围