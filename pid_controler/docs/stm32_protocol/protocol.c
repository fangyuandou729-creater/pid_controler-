/**
 * @file protocol.c
 * @brief PID控制上位机通信协议实现 - STM32 HAL版
 */

#include "protocol.h"

/* 全局变量 */
ProtocolCtx_t g_protocol;
PidParams_t g_pid_outer = {1.0f, 0.1f, 0.01f};
PidParams_t g_pid_inner = {2.0f, 0.5f, 0.0f};
ControlCmd_t g_ctrl_cmd = {0, MODE_SPEED, 0};

void Protocol_Init(void)
{
    memset(&g_protocol, 0, sizeof(ProtocolCtx_t));
    g_protocol.state = STATE_IDLE;
}

float BytesToFloat(uint8_t *bytes)
{
    float val;
    memcpy(&val, bytes, 4);
    return val;
}

void FloatToBytes(float val, uint8_t *bytes)
{
    memcpy(bytes, &val, 4);
}

void Protocol_ParseByte(uint8_t byte)
{
    ProtocolCtx_t *ctx = &g_protocol;

    switch (ctx->state) {
    case STATE_IDLE:
        if (byte == FRAME_HEADER_1)
            ctx->state = STATE_HEADER_2;
        break;

    case STATE_HEADER_2:
        ctx->state = (byte == FRAME_HEADER_2) ? STATE_LENGTH : STATE_IDLE;
        break;

    case STATE_LENGTH:
        ctx->data_len = byte;
        ctx->checksum = byte;
        ctx->state = STATE_CMD;
        break;

    case STATE_CMD:
        ctx->cmd = byte;
        ctx->checksum ^= byte;
        ctx->data_index = 0;
        ctx->state = (ctx->data_len > 4) ? STATE_DATA : STATE_CHECKSUM;
        break;

    case STATE_DATA:
        if (ctx->data_index < RX_BUF_SIZE) {
            ctx->rx_buf[ctx->data_index++] = byte;
            ctx->checksum ^= byte;
        }
        if (ctx->data_index >= (uint8_t)(ctx->data_len - 4))
            ctx->state = STATE_CHECKSUM;
        break;

    case STATE_CHECKSUM:
        ctx->state = (byte == (ctx->checksum & 0xFF)) ? STATE_TAIL_1 : STATE_IDLE;
        break;

    case STATE_TAIL_1:
        ctx->state = (byte == FRAME_TAIL_1) ? STATE_TAIL_2 : STATE_IDLE;
        break;

    case STATE_TAIL_2:
        if (byte == FRAME_TAIL_2)
            Protocol_ProcessFrame(ctx->cmd, ctx->rx_buf, ctx->data_len - 4);
        ctx->state = STATE_IDLE;
        break;

    default:
        ctx->state = STATE_IDLE;
        break;
    }
}

void Protocol_ProcessFrame(uint8_t cmd, uint8_t *data, uint8_t len)
{
    switch (cmd) {
    case CMD_SET_PID_PARAMS:
        if (len >= 13) {
            uint8_t loop_id = data[0];
            float kp = BytesToFloat(&data[1]);
            float ki = BytesToFloat(&data[5]);
            float kd = BytesToFloat(&data[9]);
            if (loop_id == 0) {
                g_pid_outer.kp = kp; g_pid_outer.ki = ki; g_pid_outer.kd = kd;
            } else {
                g_pid_inner.kp = kp; g_pid_inner.ki = ki; g_pid_inner.kd = kd;
            }
        }
        break;
    case CMD_SET_TARGET:
        if (len >= 4) g_ctrl_cmd.target = BytesToFloat(data);
        break;
    case CMD_SET_MODE:
        if (len >= 1) g_ctrl_cmd.mode = data[0];
        break;
    case CMD_START_STOP:
        if (len >= 1) g_ctrl_cmd.start_stop = data[0];
        break;
    default:
        break;
    }
}

void Protocol_SendDataReport(float measurement, float output, float setpoint, float feedback)
{
    uint8_t frame[32], data[16];
    uint8_t idx = 0, cs = 0;

    FloatToBytes(measurement, &data[0]);
    FloatToBytes(output, &data[4]);
    FloatToBytes(setpoint, &data[8]);
    FloatToBytes(feedback, &data[12]);

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

    /* 调用你的串口发送函数，例如: */
    /* HAL_UART_Transmit(&huart1, frame, idx, 100); */
}