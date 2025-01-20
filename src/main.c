/*
 * Copyright (c) 2017 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/sys/printk.h>
#include <stdlib.h>
#include <zephyr/kernel.h>

#include <zephyr/shell/shell.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/mesh.h>
#include <zephyr/bluetooth/mesh/shell.h>
#include <stdio.h>


/* Model Operation Codes */
#define BT_MESH_MODEL_OP_GEN_ONOFF_GET       BT_MESH_MODEL_OP_2(0x82, 0x01)
#define BT_MESH_MODEL_OP_GEN_ONOFF_SET       BT_MESH_MODEL_OP_2(0x82, 0x02)
#define BT_MESH_MODEL_OP_GEN_ONOFF_SET_UNACK BT_MESH_MODEL_OP_2(0x82, 0x03)
#define BT_MESH_MODEL_OP_GEN_ONOFF_STATUS    BT_MESH_MODEL_OP_2(0x82, 0x04)


static struct bt_mesh_cfg_cli cfg_cli;

static const char *onoff_str[] = { "Off", "On" };

/* Generic OnOff Server State */
struct led_onoff_state {
    const struct gpio_dt_spec led_device;
    uint8_t current;
    uint8_t previous;
};

static struct {
	bool val;
	uint8_t tid;
	uint16_t src;
	uint32_t transition_time;
	struct k_work_delayable work;
} onoff;

static struct led_onoff_state led_onoff_state = {
    .led_device = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios),
    .current = 0,
    .previous = 0,
};

static const struct gpio_dt_spec button_device = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static struct gpio_callback button_cb;

static const uint32_t time_res[] = {
	100,
	MSEC_PER_SEC,
	10 * MSEC_PER_SEC,
	10 * 60 * MSEC_PER_SEC,
};

static inline int32_t model_time_decode(uint8_t val)
{
	uint8_t resolution = (val >> 6) & BIT_MASK(2);
	uint8_t steps = val & BIT_MASK(6);

	if (steps == 0x3f) {
		return SYS_FOREVER_MS;
	}

	return steps * time_res[resolution];
}

static inline uint8_t model_time_encode(int32_t ms)
{
	if (ms == SYS_FOREVER_MS) {
		return 0x3f;
	}

	for (int i = 0; i < ARRAY_SIZE(time_res); i++) {
		if (ms >= BIT_MASK(6) * time_res[i]) {
			continue;
		}

		uint8_t steps = DIV_ROUND_UP(ms, time_res[i]);

		return steps | (i << 6);
	}

	return 0x3f;
}

static int onoff_status_send(const struct bt_mesh_model *model,
			     struct bt_mesh_msg_ctx *ctx)
{
	uint32_t remaining;

	BT_MESH_MODEL_BUF_DEFINE(buf, BT_MESH_MODEL_OP_GEN_ONOFF_STATUS, 3);
	bt_mesh_model_msg_init(&buf, BT_MESH_MODEL_OP_GEN_ONOFF_STATUS);

	remaining = k_ticks_to_ms_floor32(
			    k_work_delayable_remaining_get(&onoff.work)) +
		    onoff.transition_time;

	/* Check using remaining time instead of "work pending" to make the
	 * onoff status send the right value on instant transitions. As the
	 * work item is executed in a lower priority than the mesh message
	 * handler, the work will be pending even on instant transitions.
	 */
	if (remaining) {
		net_buf_simple_add_u8(&buf, !onoff.val);
		net_buf_simple_add_u8(&buf, onoff.val);
		net_buf_simple_add_u8(&buf, model_time_encode(remaining));
	} else {
		net_buf_simple_add_u8(&buf, onoff.val);
	}

	return bt_mesh_model_send(model, ctx, &buf, NULL, NULL);
}

static int gen_onoff_get(const struct bt_mesh_model *model,
                         struct bt_mesh_msg_ctx *ctx,
                         struct net_buf_simple *buf)
{
    NET_BUF_SIMPLE_DEFINE(msg, 2 + 1 + 4);
    struct led_onoff_state *state = &led_onoff_state;

    printk("OnOff Get: LED state is %u\n", state->current);

    bt_mesh_model_msg_init(&msg, BT_MESH_MODEL_OP_GEN_ONOFF_STATUS);
    net_buf_simple_add_u8(&msg, state->current);
    // onoff_status_send(model, ctx);

    int err = bt_mesh_model_send(model, ctx, &msg, NULL, NULL);
    if (err) {
        printk("Unable to send OnOff Status response (err %d)\n", err);
        return err;
    }

    return 0;
}

static int gen_onoff_set(const struct bt_mesh_model *model,
                         struct bt_mesh_msg_ctx *ctx,
                         struct net_buf_simple *buf)
{
    struct led_onoff_state *state = &led_onoff_state;
    uint8_t new_state = net_buf_simple_pull_u8(buf);

    printk("OnOff Set: Setting LED state to %u\n", new_state);

    state->current = new_state;
    gpio_pin_set_dt(&state->led_device, state->current);
    onoff_status_send(model, ctx);

    gen_onoff_get(model, ctx, buf);

    return 0;
}

static int gen_onoff_status(const struct bt_mesh_model *model,
                            struct bt_mesh_msg_ctx *ctx,
                            struct net_buf_simple *buf)
{
    uint8_t present = net_buf_simple_pull_u8(buf);  // Get the current OnOff state
    printk("Received OnOff Status: %s\n", present ? "ON" : "OFF");

    // Ensure led_onoff_state is initialized (assuming it's globally defined somewhere)
    struct led_onoff_state *state = &led_onoff_state;

    // If there's additional information (target state and remaining time)
    if (buf->len) {
        uint8_t target = net_buf_simple_pull_u8(buf);  // Get the target state
        int32_t remaining_time = model_time_decode(net_buf_simple_pull_u8(buf));  // Get remaining time for transition

        printk("OnOff status: %s -> %s: (%d ms)\n",
               onoff_str[state->current],  // Current state
               onoff_str[target],  // Target state
               remaining_time);  // Transition time (in ms)
        
        // You might want to update state->current based on the target state
        state->current = target;

        return 0;
    }

    // If no target state or time is provided, just print the current state
    printk("OnOff status: %s\n", onoff_str[state->current]);

    return 0;
}

static int gen_onoff_set_unack(const struct bt_mesh_model *model,
                               struct bt_mesh_msg_ctx *ctx,
                               struct net_buf_simple *buf)
{
    struct led_onoff_state *state = &led_onoff_state;
    uint8_t new_state = net_buf_simple_pull_u8(buf);

    printk("OnOff Set Unack: Setting LED state to %u\n", new_state);

    state->current = new_state;
    gpio_pin_set_dt(&state->led_device, state->current);

    return 0;
}

static const struct bt_mesh_model_op gen_onoff_srv_op[] = {
    { BT_MESH_MODEL_OP_GEN_ONOFF_GET,       BT_MESH_LEN_EXACT(0), gen_onoff_get },
    { BT_MESH_MODEL_OP_GEN_ONOFF_SET,       BT_MESH_LEN_EXACT(2), gen_onoff_set },
    { BT_MESH_MODEL_OP_GEN_ONOFF_SET_UNACK, BT_MESH_LEN_EXACT(2), gen_onoff_set_unack },
    BT_MESH_MODEL_OP_END,
};

static const struct bt_mesh_model_op gen_onoff_cli_op[] = {
    { BT_MESH_MODEL_OP_GEN_ONOFF_STATUS, BT_MESH_LEN_EXACT(1), gen_onoff_status },
    BT_MESH_MODEL_OP_END,
};

#if defined(CONFIG_BT_MESH_DFD_SRV)
static struct bt_mesh_dfd_srv dfd_srv;
#endif

#if defined(CONFIG_BT_MESH_SAR_CFG_CLI)
static struct bt_mesh_sar_cfg_cli sar_cfg_cli;
#endif

#if defined(CONFIG_BT_MESH_PRIV_BEACON_CLI)
static struct bt_mesh_priv_beacon_cli priv_beacon_cli;
#endif

#if defined(CONFIG_BT_MESH_SOL_PDU_RPL_CLI)
static struct bt_mesh_sol_pdu_rpl_cli srpl_cli;
#endif


#if defined(CONFIG_BT_MESH_OD_PRIV_PROXY_CLI)
static struct bt_mesh_od_priv_proxy_cli od_priv_proxy_cli;
#endif

#if defined(CONFIG_BT_MESH_LARGE_COMP_DATA_CLI)
struct bt_mesh_large_comp_data_cli large_comp_data_cli;
#endif

BT_MESH_SHELL_HEALTH_PUB_DEFINE(health_pub);
BT_MESH_MODEL_PUB_DEFINE(gen_onoff_pub_srv, NULL, 2 + 2);

static const struct bt_mesh_model root_models[] = {
    BT_MESH_MODEL_CFG_SRV,
	BT_MESH_MODEL_CFG_CLI(&cfg_cli),
	BT_MESH_MODEL_HEALTH_SRV(&bt_mesh_shell_health_srv, &health_pub,
				 health_srv_meta),
	BT_MESH_MODEL_HEALTH_CLI(&bt_mesh_shell_health_cli),
    BT_MESH_MODEL(BT_MESH_MODEL_ID_GEN_ONOFF_SRV, gen_onoff_srv_op,
                  &gen_onoff_pub_srv, NULL),
	BT_MESH_MODEL(BT_MESH_MODEL_ID_GEN_ONOFF_CLI, gen_onoff_cli_op,
		      NULL, NULL),
#if defined(CONFIG_BT_MESH_DFD_SRV)
	BT_MESH_MODEL_DFD_SRV(&dfd_srv),
#else
#if defined(CONFIG_BT_MESH_SHELL_DFU_SRV)
	BT_MESH_MODEL_DFU_SRV(&bt_mesh_shell_dfu_srv),
#elif defined(CONFIG_BT_MESH_SHELL_BLOB_SRV)
	BT_MESH_MODEL_BLOB_SRV(&bt_mesh_shell_blob_srv),
#endif
#if defined(CONFIG_BT_MESH_SHELL_DFU_CLI)
	BT_MESH_MODEL_DFU_CLI(&bt_mesh_shell_dfu_cli),
#elif defined(CONFIG_BT_MESH_SHELL_BLOB_CLI)
	BT_MESH_MODEL_BLOB_CLI(&bt_mesh_shell_blob_cli),
#endif
#endif /* CONFIG_BT_MESH_DFD_SRV */
#if defined(CONFIG_BT_MESH_SHELL_RPR_CLI)
	BT_MESH_MODEL_RPR_CLI(&bt_mesh_shell_rpr_cli),
#endif
#if defined(CONFIG_BT_MESH_RPR_SRV)
	BT_MESH_MODEL_RPR_SRV,
#endif

#if defined(CONFIG_BT_MESH_SAR_CFG_SRV)
	BT_MESH_MODEL_SAR_CFG_SRV,
#endif
#if defined(CONFIG_BT_MESH_SAR_CFG_CLI)
	BT_MESH_MODEL_SAR_CFG_CLI(&sar_cfg_cli),
#endif

#if defined(CONFIG_BT_MESH_OP_AGG_SRV)
	BT_MESH_MODEL_OP_AGG_SRV,
#endif
#if defined(CONFIG_BT_MESH_OP_AGG_CLI)
	BT_MESH_MODEL_OP_AGG_CLI,
#endif

#if defined(CONFIG_BT_MESH_LARGE_COMP_DATA_SRV)
	BT_MESH_MODEL_LARGE_COMP_DATA_SRV,
#endif
#if defined(CONFIG_BT_MESH_LARGE_COMP_DATA_CLI)
	BT_MESH_MODEL_LARGE_COMP_DATA_CLI(&large_comp_data_cli),
#endif

#if defined(CONFIG_BT_MESH_PRIV_BEACON_SRV)
	BT_MESH_MODEL_PRIV_BEACON_SRV,
#endif
#if defined(CONFIG_BT_MESH_PRIV_BEACON_CLI)
	BT_MESH_MODEL_PRIV_BEACON_CLI(&priv_beacon_cli),
#endif
#if defined(CONFIG_BT_MESH_OD_PRIV_PROXY_CLI)
	BT_MESH_MODEL_OD_PRIV_PROXY_CLI(&od_priv_proxy_cli),
#endif
#if defined(CONFIG_BT_MESH_SOL_PDU_RPL_CLI)
	BT_MESH_MODEL_SOL_PDU_RPL_CLI(&srpl_cli),
#endif
#if defined(CONFIG_BT_MESH_OD_PRIV_PROXY_SRV)
	BT_MESH_MODEL_OD_PRIV_PROXY_SRV,
#endif
};

static const struct bt_mesh_elem elements[] = {
	BT_MESH_ELEM(0, root_models, BT_MESH_MODEL_NONE),
};

static const struct bt_mesh_comp comp = {
	.cid = CONFIG_BT_COMPANY_ID,
	.elem = elements,
	.elem_count = ARRAY_SIZE(elements),
};

static int gen_onoff_send(bool val)
{
    struct bt_mesh_msg_ctx ctx = {
        .app_idx = root_models[5].keys[0],
        .addr = BT_MESH_ADDR_ALL_NODES,
        .send_ttl = BT_MESH_TTL_DEFAULT,
    };
    static uint8_t tid;

    if (ctx.app_idx == BT_MESH_KEY_UNUSED) {
        printk("The Generic OnOff Client must be bound to a key before sending.\n");
        return -ENOENT;
    }

    BT_MESH_MODEL_BUF_DEFINE(buf, BT_MESH_MODEL_OP_GEN_ONOFF_SET_UNACK, 2);
    bt_mesh_model_msg_init(&buf, BT_MESH_MODEL_OP_GEN_ONOFF_SET_UNACK);
    net_buf_simple_add_u8(&buf, val);
    net_buf_simple_add_u8(&buf, tid++);

    printk("Sending OnOff Set: %s\n", onoff_str[val]);

    return bt_mesh_model_send(&root_models[5], &ctx, &buf, NULL, NULL);
}

static void button_pressed_callback(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
    printk("Button press detected\n");

    if (bt_mesh_is_provisioned()) {
		onoff.val = !onoff.val;

		led_onoff_state.current = onoff.val;
        (void)gen_onoff_send(onoff.val);
    } else {
        printk("Device not provisioned. Please provision it first.\n");
    }
}

static void button_init(void)
{
    if (!device_is_ready(button_device.port)) {
        printk("Error: Button device is not ready\n");
        return;
    }

    gpio_pin_configure_dt(&button_device, GPIO_INPUT);
    gpio_pin_interrupt_configure_dt(&button_device, GPIO_INT_EDGE_TO_ACTIVE);
	gpio_pin_set(led_onoff_state.led_device.port, led_onoff_state.led_device.pin, led_onoff_state.current);
	led_onoff_state.current = 0;
    gpio_init_callback(&button_cb, button_pressed_callback, BIT(button_device.pin));
    gpio_add_callback(button_device.port, &button_cb);

    printk("Button initialized\n");
}

void enable_ADV(void)
{
	int err;
	err = bt_mesh_prov_enable(BT_MESH_PROV_ADV);
	if (err != 0) {
		printk("ADV initialization failed\n");
	}  else {
		printk("ADV initialized\n");
	}
}

void disable_ADV(void)
{
	int err;
	err = bt_mesh_prov_disable(BT_MESH_PROV_ADV);
	if (err != 0) {
		printk("ADV disabling failed\n");
	}  else {
		printk("ADV disabled\n");
	}
}

static void bt_ready(int err)
{
	if (err && err != -EALREADY) {
		printk("Bluetooth init failed (err %d)\n", err);
		return;
	}

	printk("Bluetooth initialized\n");

	err = bt_mesh_init(&bt_mesh_shell_prov, &comp);
	if (err) {
		printk("Initializing mesh failed (err %d)\n", err);
		return;
	}

	if (IS_ENABLED(CONFIG_SETTINGS)) {
		settings_load();
	}

	printk("Mesh initialized\n");

	enable_ADV();

	if (bt_mesh_is_provisioned()) {
		printk("Mesh network restored from flash\n");
		disable_ADV();
	} else {
		printk("Use \"prov pb-adv on\" or \"prov pb-gatt on\" to "
			    "enable advertising\n");
	}
}

int main(void)
{
	int err;

	printk("Initializing...\n");

    /* Initialize LED */
    if (!gpio_is_ready_dt(&led_onoff_state.led_device)) {
        printk("LED device not ready\n");
        return -1;
    }

    gpio_pin_configure_dt(&led_onoff_state.led_device, GPIO_OUTPUT_INACTIVE);
    button_init();

	/* Initialize the Bluetooth Subsystem */
	err = bt_enable(bt_ready);
	if (err && err != -EALREADY) {
		printk("Bluetooth init failed (err %d)\n", err);
	}
    
	printk("Press the <Tab> button for supported commands.\n");
	printk("Before any Mesh commands you must run \"mesh init\"\n");
	return 0;
}