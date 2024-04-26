# Script to read powermeter values from a DDSU Hoymiles compatible
# Needs "pymodbus" (it is a full Modbus protocol) to be installed, e.g. "pip install pymodbus"
# Usage: GetPowerFromDDSU666 <Device_Number>

from pymodbus.client import ModbusSerialClient as ModbusClient
import struct
import sys
import time

# Function to read registers with retry mechanism
def read_registers_with_retry(client, register_address, num_registers, unit):
    max_retries = 3
    retries = 0
    while retries < max_retries:
        result = client.read_input_registers(register_address, num_registers, unit=unit)
        if not result.isError():
            return result
        else:
            print("Error reading registers. Retrying...")
            retries += 1
            time.sleep(1)  # Wait for 1 second before retrying
    print("Failed to read registers after {} retries.".format(max_retries))
    return None

def GetPower(device_address):
    # Modbus RTU Client configuration
    client = ModbusClient(method='rtu', port='/dev/ttyUSB0', baudrate=9600, timeout=1)

    # Register number to be read (0x2004) which is 
    register_address = 0x2004  # DDSU666_POWER

    # Number of registers to be read (2 for a float)
    num_registers = 2

    # Open the connection 
    client.connect()

    # Read the register
    result = read_registers_with_retry(client, register_address, num_registers, int(device_address))

    # If reading was successful, continue processing
    if result is not None:
        # Combine the 2 registers into one 32-bit value 
        combined_value = (result.registers[0] << 16) + result.registers[1]

        # Interpret value as a float * 1000 because of KW value returned
        interpreted_value = struct.unpack('>f', struct.pack('>I', combined_value))[0] * 1000

        # Invert the sign if interpreted_value
        interpreted_value *= -1

        # Convert interpreted_value to an integer to display only the numbers before the decimal point
        AC_GRID = int(interpreted_value)

    # Print interpreted value for debugging purpose
    #print("Interpreted value of register 0x2004 for DDSU666:", AC_GRID, "W")

    # Close the connection
    client.close()
