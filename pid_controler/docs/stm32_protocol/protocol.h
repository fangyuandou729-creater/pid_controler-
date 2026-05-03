/**
 * @file protocol.h
 * @brief PID控制上位机通信协议 - STM32 HAL版
 * @note  适配"模仿者小队"直流减速电机闭环控制上位机
 *        协议格式: [帧头 0xAA55][长度][命令][数据][XOR校验][帧尾 0x55AA]
 */

#ifndef __PROTOCOL_H
#define __PROTOCOL_H

#include <stdint.h>
#include <string.h>

/* 帧头帧尾 */
#define FRAME_HEADER_1  0xAA
#define FRAME_HEADER_2  0x55
#define FRAME_TAIL_1    0x55
#define FRAME_TAIL_2    0xAA

/* 命令类型 */
#define CMD_SET_PID_PARAMS  0x01   /* PC→MCU: 设置PID参数 */
#define CMD_SET_TARGET      0x02   /* PC→MCU: 设置目标值 */
#define CMD_SET_MODE        0x03   /* PC→MCU: 设置控制模式 */
#define CMD_START_STOP      0x04   /* PC→MCU: 启停控制 */
#define CMD_QUERY_STATUS    0x05   /* PC→MCU: 查询状态 */
#define CMD_DATA_REPORT     0x81   /* MCU→PC: 数据上报 */

/* 控制模式 */
#define MODE_SPEED      0   /* 速度环 */
#define MODE_POSITION   1   /* 位置环 */
#define MODE_ANGLE      2   /* 角度环 */
#define MODE_CASCADE    3   /* 串级控制 */

#define RX_BUF_SIZE     128

/* 帧解析状态机 */
typedef enum {
    STATE_IDLE, STATE_HEADER_2, STATE_LENGTH, STATE_CMD,
    STATE_DATA, STATE_CHECKSUM, STATE_TAIL_1, STATE_TAIL_2
} ParseState;

/* PID参数 */
typedef struct {
    float kp;
    float ki;
    float kd;
} PidParams_t;

/* 控制指令 */
typedef struct {
    float target;
    uint8_t mode;
    uint8_t start_stop;
} ControlCmd_t;

/* 协议上下文 */
typedef struct {
    ParseState state;
    uint8_t rx_buf[RX_BUF_SIZE];
    uint8_t data_len;
    uint8_t cmd;
    uint8_t data_index;
    uint8_t checksum;
} ProtocolCtx_t;

/* 全局变量 */
extern ProtocolCtx_t g_protocol;
extern PidParams_t g_pid_outer;
extern PidParams_t g_pid_inner;
extern ControlCmd_t g_ctrl_cmd;

/* 函数 */
void Protocol_Init(void);
void Protocol_ParseByte(uint8_t byte);
void Protocol_ProcessFrame(uint8_t cmd, uint8_t *data, uint8_t len);
float BytesToFloat(uint8_t *bytes);
void FloatToBytes(float val, uint8_t *bytes);
void Protocol_SendDataReport(float measurement, float output, float setpoint, float feedback);

#endif