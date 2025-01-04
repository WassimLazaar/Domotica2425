#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/util.h>
#include <zephyr/sys/printk.h>
#include <zephyr/drivers/uart.h>
#include <string.h>

/* change this to any other UART peripheral if desired */
#define UART_DEVICE_NODE DT_CHOSEN(zephyr_shell_uart)
static const struct device *const uart_dev = DEVICE_DT_GET(UART_DEVICE_NODE);


#define LED0_NODE DT_ALIAS(led0)
#define LED1_NODE DT_ALIAS(led1)

#if !DT_NODE_HAS_STATUS(LED0_NODE, okay)
#error "Unsupported board: led0 devicetree alias is not defined"
#endif

#if !DT_NODE_HAS_STATUS(LED1_NODE, okay)
#error "Unsupported board: led1 devicetree alias is not defined"
#endif 

struct led {
    struct gpio_dt_spec spec;
    uint8_t num;
};

static const struct led led0 = {
    .spec = GPIO_DT_SPEC_GET_OR(LED0_NODE, gpios, {0}),
    .num = 0,
};

static const struct led led1 = {
    .spec = GPIO_DT_SPEC_GET_OR(LED1_NODE, gpios, {0}),
    .num = 1,
}; 

/* UART Buffer */
#define UART_BUF_SIZE 64
static char uart_buffer[UART_BUF_SIZE];
static size_t uart_buffer_pos = 0;


/* Callback voor UART ontvangst */
static void uart_callback(const struct device *dev, void *user_data)
{
    uint8_t c;
    while (uart_fifo_read(dev, &c, 1) > 0) {
       
        if (c == '\n' || c == '\r') {
            uart_buffer[uart_buffer_pos] = '\0'; // Sluit de string af
            uart_buffer_pos = 0; // Reset de bufferpositie
        } else if (uart_buffer_pos < UART_BUF_SIZE - 1) {
            uart_buffer[uart_buffer_pos++] = c;
        }
        
    }
}

int main(void)
{
    int ret;
    int ret1;

    /* Controleer UART */
    if (!device_is_ready(uart_dev)) {
        printk("Error: UART device is not ready\n");
        return 0;
    }
    uart_irq_callback_user_data_set(uart_dev, uart_callback, NULL);
    uart_irq_rx_enable(uart_dev);

    /* Configureer LED0 */
    if (!device_is_ready(led0.spec.port)) {
        printk("Error: LED0 device is not ready\n");
        return 0;
    }
    ret = gpio_pin_configure_dt(&led0.spec, GPIO_OUTPUT);
    if (ret < 0) {
        printk("Error %d: Failed to configure LED0\n", ret);
        return 0;
    }

    /* Configureer LED1 */
    if (!device_is_ready(led1.spec.port)) {
        printk("Error: LED1 device is not ready\n");
        return 0;
    }
    ret1 = gpio_pin_configure_dt(&led1.spec, GPIO_OUTPUT);
    if (ret < 0) {
        printk("Error %d: Failed to configure LED1\n", ret1);
        return 0;
    }

   char local_buffer[UART_BUF_SIZE];
   uart_buffer[0] = '\0'; // Reset de buffer
   gpio_pin_set(led1.spec.port, led1.spec.pin, 0); // LED1 uit
   gpio_pin_set(led0.spec.port, led0.spec.pin, 0); // LED0 uit
    /* Eindeloze lus om LED's aan/uit te schakelen */
    while (1) {
        

        strncpy(local_buffer, uart_buffer, UART_BUF_SIZE);
        
    
        if (strcmp(local_buffer, "led0aan") == 0) {
            gpio_pin_set(led0.spec.port, led0.spec.pin, 1); // LED0 aan
        } else if (strcmp(local_buffer, "led1aan") == 0) {
            gpio_pin_set(led1.spec.port, led1.spec.pin, 1); // LED1 aan
        } else if (strcmp(local_buffer, "led0uit") == 0) {
            gpio_pin_set(led0.spec.port, led0.spec.pin, 0); // LED0 uit
        } else if (strcmp(local_buffer, "led1uit") == 0) {
            gpio_pin_set(led1.spec.port, led1.spec.pin, 0); // LED1 uit
        }

        //k_sleep(K_MSEC(100)); // Kleine pauze om CPU-gebruik te minimaliseren
    }

    return 0;
}
