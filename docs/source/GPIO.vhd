----------------------------------------------------------------------------------
-- @file
-- Company: Mc Gill University
-- Engineer: J.-F. Cliche
--
-- Create Date:    2011-08-24
-- Design Name:    chFPGA
-- Module Name:    GPIO - Behavioral
-- Project Name:
-- Target Devices: Virtex 6 or 7 series
-- Tool versions: ISE 13.1 - 14.2
--
-- Dependencies:
--
-- Revision:
--  2011-08-29 JFC: Added USER_ACCESS to obtain the bitstream date (or other user info inserted at bitstream-generation time)
--  2011-09-14 JFC: Added global reset signal
--  2012-09-18 JFC: Cleanup. Added comments. Removed version Generics
--  2012-09-23 JFC: Moved fan readout (debouncing) circuitry in here.
--  2012-11-05 JFC: Removed RST from the fan tachymeter measurment logic to slightly reduce logic.
--  2013-01-30 JFC: Added PLATFORM_ID field to allow the Python software to instantiate the appropriate handlers for the specific platform
----------------------------------------------------------------------------------
library IEEE;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_misc.all; -- for or_reduce()


use work.chFPGA_Package.all; -- Get all component definitions

use work.icecore_package.slv32_array;
use work.icecore_package.irigb;

library UNISIM;
use UNISIM.VComponents.all;

library xpm;
use xpm.vcomponents.all;

-- Implements general I/O common to all the devices
--
-- Includes
--   - Global data capture/injection trigger
--   - Global antenna reset
--   - Global correlator reset
--   - LCD Interface bits
--   - Buck switching supply SYNC signal generation
--   - FMC ADC Reset line
--   - Fan speed readout
--   - IP Port offsets for the data capture and correlator outputs
entity GPIO is
	generic (
		PLATFORM_ID: INTEGER; --! identifies the type of platform on which the firmware is running
		COOKIE : integer := 16#42#;
		PROTOCOL_VERSION: INTEGER; --! Protocol version used to determins compatibility with the python support software
		NUMBER_OF_ADCS: INTEGER; --! Number of antenna processing blocks that are implemented
		NUMBER_OF_CHANNELIZERS: INTEGER; --! Number of antenna processing blocks that are implemented
		CHANNELIZERS_CLOCK_SOURCE: INTEGER; --! ADC channel from which the channelizers clocks are derived
		NUMBER_OF_CHANNELIZERS_WITH_FFT: INTEGER; --! Number of antenna processing blocks with an FFT module
		ADC_SAMPLES_PER_FRAME: integer;
		ADC_SAMPLES_PER_WORD: integer;
		ADC_BITS_PER_SAMPLE: integer;
		NUMBER_OF_CROSSBAR_INPUTS: integer;
		NUMBER_OF_CROSSBAR1_OUTPUTS: integer;
		NUMBER_OF_BP_SHUFFLE_LINKS: integer;
		NUMBER_OF_GPU_LINKS: integer;
		NUMBER_OF_CORRELATORS: INTEGER; --! Number of correlator blocks (CH_DIST+CORR+ACC) that are implemented if IMPLEMENT_CORR=TRUE
		NUMBER_OF_CHANNELIZERS_TO_CORRELATE: INTEGER; --! Number of antennas to be correlated for each frequency channel. This is hard coded for now. Determines how many antenna streams are fed to the CORR_BLOCK modules, and how many multipliers to implement in parallel in the CORR module.
		NUMBER_OF_ADC_BOARDS: integer := 1;
		NUMBER_OF_BUCK_SYNC_LINES: integer :=16;
		BUCK_SYNC_ENABLE: boolean := True; -- default state of the buck sync enable at startup
		BUCK_CLK_DIVIDE_FACTOR: INTEGER :=12; -- Buck frequency is 200MHz/BUCK_CLK_DIVIDE_FACTOR/16
		MAC_ADDRESS_OUI_CODE: std_logic_vector(23 downto 0) := X"000A35"; -- Xilinx OUI code used to identify the first 3 bytes of the MAC address
		NUMBER_OF_USER_SMA_SIGNALS: integer := 8;
		IMPLEMENT_LCD: BOOLEAN := FALSE;
		IMPLEMENT_SWITCHER_SYNC: BOOLEAN := TRUE;
		IMPLEMENT_FAN: BOOLEAN := TRUE;
		IMPLEMENT_ARM_SPI: BOOLEAN := TRUE;
		SIM: boolean := FALSE
		);
	port (
		-- Control interface

		ctrl_cmd_in_dat: in AXIS8_DAT_STRUCT; -- Command stream input, signals from master (Data, Valid, Last)
		ctrl_cmd_in_rdy: out AXIS8_RDY_STRUCT; -- Command stream input, signals to master (Ready)
		ctrl_rply_out_dat: out AXIS8_DAT_STRUCT; -- Reply stream output, signals to slave (Data, Valid, Last)
		ctrl_rply_out_rdy: in AXIS8_RDY_STRUCT; -- Reply stream output,  signals from slave (Ready)
		ctrl_clk: in  std_logic;
		ctrl_rst: in std_logic;

		-- IP Port setting

		HOST_FRAME_READ_RATE: out std_logic_vector(4 downto 0);

		-- UDP local Rx networking configuration
		local_mac_addr: out std_logic_vector(47 downto 0);
		local_base_ip_addr: out std_logic_vector(31 downto 0);
		local_base_ip_port: out std_logic_vector(15 downto 0);
		local_subarray: out std_logic_vector(1 downto 0);
		-- UDP TX channel 0 remote network configuration
		--   MAC & IP addresses are hardwired to be those of the perviously received packet
		remote_ip_port0: out std_logic_vector(15 downto 0); -- normally set to zero to reply to the same port as the last command

		-- UDP TX channel 1 remote network configuration
		remote_mac_addr1: out std_logic_vector(47 downto 0);
		remote_ip_addr1: out std_logic_vector(31 downto 0);
		remote_ip_port1: out std_logic_vector(15 downto 0);

		-- Buck control signals

		buck_sync: out std_logic_vector(0 to NUMBER_OF_BUCK_SYNC_LINES-1);

		-- ARM SPI interface

		arm_spi_sck: in std_logic;
		arm_spi_miso: out std_logic;
		arm_spi_mosi: in std_logic;
		arm_spi_cs_n: in std_logic;

		-- Various unused signals, defined for testing

		arm_irq_in: in std_logic;
		arm_irq_out: out std_logic;
		arm_irq_oe: out std_logic;

		flash_cs_in: in std_logic;
		flash_cs_out: out std_logic;
		flash_cs_oe: out std_logic;

		gpio_irq_in: in std_logic;
		gpio_irq_out: out std_logic;
		gpio_irq_oe: out std_logic;  -- Active-high: enables GPIO reset output driver.

		gpio_rst_in: in std_logic;
		gpio_rst_out: out std_logic;
		gpio_rst_oe: out std_logic;  -- Active-high: enables GPIO reset output driver.

		uart_rx_in: in std_logic;
		uart_rx_out: out std_logic;
		uart_rx_oe: out std_logic;

		uart_tx_in: in std_logic;
		uart_tx_out: out std_logic;
		uart_tx_oe: out std_logic;

		-- FAN control signals (for on-board fan found on some evaluation boards)

		FAN_PWM: out std_logic; --! PWM control of the fan
		FAN_TACH: in std_logic; --! Tachymeter input from the fan (two pulses per revolution). A debouncer cleans this signal before measuring the fan frequency.
		FAN_TACH_DIV2: out std_logic; --! logic signal pulsing at half the fan rotation speed

		-- ADC mezzanine control signals

		ADC_RST: out std_logic_vector(0 to NUMBER_OF_ADC_BOARDS-1);
		adc_cal_freeze: out std_logic_vector(0 to 7);
		adc_cal_frozen: in std_logic_vector(0 to 7) := (others => '0');
		adc_cal_signal_detect: in std_logic_vector(0 to 7) := (others => '0');

		adc_pll_lock: in std_logic_vector(0 to NUMBER_OF_ADC_BOARDS-1); --! Lock signal for the ADC PLL on each mezzanine

		-- LCD (on some evaluation boards)

		LCD_DB: out  std_logic_vector(7 downto 4);
		LCD_E : out  std_logic;
		LCD_RS : out  std_logic;
		LCD_RW : out  std_logic;

		-- Backplane signals

		-- Slot sensing system (measures capacitance on the sense line to identify the slot number)

		slot_probe: in std_logic_vector(1 downto 0); --! Signal used to probe the capacitance of the backplane slot-sense line
		slot_sense: in std_logic_vector( 1 downto 0); --! Returns the logic level change in response to the probe edge, which is used to determine the board capacitance.

		-- Backplane synchronization signal

		bp_buck_sync: inout std_logic;
		bp_buck_sync_mon: out std_logic;

		-- Backplane global interrupt line

		bp_gpio_int_out: out std_logic;
		bp_gpio_int_in: in std_logic;
		bp_gpio_int_oe: out std_logic;

		-- UDP Communication link monitoring

		udp_tx_frame : in std_logic;
		udp_rx_frame : in std_logic;
		udp_tx_overflow : in std_logic;
		udp_rx_overflow : in std_logic;
		sfp_status_vector: in std_logic_vector(15 downto 0);
		sfp_config_vector: out std_logic_vector(31 downto 0);

		cmd_packet_counter: in std_logic_vector(7 downto 0);
		rply_packet_counter: in std_logic_vector(7 downto 0);
		udp_stack_reset: out std_logic;
		ctrl_master_reset: out std_logic;

		-- General signals

		TRIG_ASYNC: out std_logic;

		-- Clocks

		clk200: in std_logic; --! 200 MHz clock, used for many things
		clk200_reset: in std_logic; --!
		clk10: in std_logic; --! 10 MHZ reference clock, in phase for every board in the system
		clk10_sel: out std_logic;
		dna_clk: in std_logic; --! DNA port clock (max 97 MHz)

        -- External PLL control

        pll_sync: out std_logic;

		-- PWM signal

		pwm_clk: in std_logic;
		pwm_ctr_en: in std_logic; -- Active when the pwm counter is to be enabled.
		pwm_reset: in std_logic;
		pwm_out: out std_logic;

		-- Event (Frame) counter

		event_ctr_clk: in std_logic;
		event_ctr_en: in std_logic;
		event_ctr_inc: in std_logic;
		event_ctr_reset: in std_logic;

		-- User output selection

		user_mux_in: in std_logic_vector(0 to NUMBER_OF_USER_SMA_SIGNALS-1); -- User selectable signals (typically PWM, 1PPS, SYNC, ?)
		user_mux_out: out std_logic_vector(0 to 3); -- User selected signal
		user_mux_oe: out std_logic_vector(0 to 3);
		user_bit: out std_logic_vector(1 downto 0);

		-- IRIG-B time

		irigb_mux_in: in std_logic_vector(0 to 7); -- IRIG-B time signals
		irigb_before_target: out std_logic;
		irigb_pps: out std_logic;
		irigb_out: out std_logic;
		irigb_delay: out std_logic_vector(4 downto 0); -- Delay to apply to the IRIG-B signals on the IOB
		irigb_delay_reset: out std_logic;

		-- Channelizer clock source selection

		CHAN_CLK_SOURCE: out std_logic;

		-- User-controlled global resets

		USER_RESET: out std_logic;
		ctrl_reset_pulse: out std_logic;
		sysmon_user_reset: out std_logic;
		ADCDAQ_RESET_ASYNC: out std_logic;
		CHAN_CLK_RESET_ASYNC: out std_logic;
		CHAN_RESET_ASYNC: out std_logic;
		CORR_RESET_ASYNC: out std_logic;
		BLINKER_RESET: out std_logic
	);
end GPIO;

architecture Behavioral of GPIO is

attribute async_reg : string;

constant FPGA_SERIES:integer := PLATFORM_INFO(PLATFORM_ID).FPGA_SERIES;
constant WORDS_PER_FRAME: integer := ADC_SAMPLES_PER_FRAME / ADC_SAMPLES_PER_WORD;
constant LOG2_WORDS_PER_FRAME: integer := integer_log2(WORDS_PER_FRAME); --! Number of words per frame. One word is 4 8-bit time samples or 2 8+8-bits frequency samples.
constant LOG2_SAMPLES_PER_FRAME: integer := integer_log2(ADC_SAMPLES_PER_FRAME);
constant LOG2_SAMPLES_PER_WORD: integer := integer_log2(ADC_SAMPLES_PER_WORD);

--signal CLK: std_logic;
signal CLK_CTR: UNSIGNED(7 downto 0):=(others=>'0'); -- Divides the ADC clock by up to 255
signal CE: std_logic:='0';

signal firmware_timestamp: std_logic_vector(31 downto 0);
signal USER_DATA_VALID: std_logic;

--- Define Control word and its signals
signal CONTROL_BYTES: slv8_array(0 to 50); -- default value set in the CMD_SLAVE
signal STATUS_BYTES: slv8_array(0 to 37); -- default value set in the CMD_SLAVE

--signal CTRL_FLAG_ADC_RESET: std_logic;
signal CTRL_FLAG_BUCK_SYNC_ENABLE: std_logic;
signal CTRL_FLAG_ADCDAQ_RESET: std_logic;
signal CTRL_FLAG_GLOBAL_TRIG: std_logic;
signal CTRL_FLAG_BUCK_CLK_DIV: UNSIGNED(7 downto 0);
signal buck_sync_int: std_logic:='0';
signal buck_phase: std_logic_vector(NUMBER_OF_BUCK_SYNC_LINES*4-1 downto 0);
signal buck_phase_ctr: unsigned(3 downto 0):=(others=>'0'); -- Counts the 16 possible phasess. Initialized to avoid metata on '=' for simulations.

--signal CTRL_FLAG_TEST: std_logic_vector(3 downto 0);
--signal CHAN_RESET_ASYNC: std_logic;
--signal CORR_RESET_ASYNC: std_logic;

-- ARM-SPI interface
	signal spi_addr, spi_rdat, spi_wdat: std_logic_vector(31 downto 0) := (others => '0');
	signal spi_rreq, spi_rack, spi_wreq, spi_wack: std_logic := '0'; -- important to have default value in case the ARM SPI receiver is not instantiated.

	constant NUMBER_OF_CORE_REGISTERS: integer := 26;
	signal core_reg_wr_value : work.icecore_package.slv32_array(0 to NUMBER_OF_CORE_REGISTERS-1);
	signal core_reg_rd_value : work.icecore_package.slv32_array(0 to NUMBER_OF_CORE_REGISTERS-1);
	constant core_reg_default_values : work.icecore_package.slv32_array(0 to NUMBER_OF_CORE_REGISTERS-1) := (
		7 => X"00000000", -- MAC
		8 => X"0000_0000", -- MAC, Port
		9 => X"00000000", -- IP
		others => X"00000000" );

-- -- ARM memory map process
-- 	-- Define module addresses
-- 	constant BASE_ADDR: integer := 0; -- Core Control register
-- 	constant NUMBER_OF_MODULES: integer := 1;

-- 	signal addr: unsigned(18 downto 0) := (others => '0');
-- 	signal addr_dly: unsigned(18 downto 0) := (others => '0');
-- 	signal din_dly: std_logic_vector(31 downto 0) := (others => '0');
-- 	-- Bus control signals for each module, packed into arrays
-- 	signal rreq, rack, wreq, wack: std_logic_vector(0 to NUMBER_OF_MODULES-1) := (others => '0');
-- 	signal dout: icecore_package.slv32_array(0 to NUMBER_OF_MODULES-1) := (others=> (others=>'0'));


-- Fan related signals
signal FAN_TACH_CTR: UNSIGNED(16 downto 0); --! the length of this counter sets the number of clk200 cycles  the debouncing waits before deciding that the state is stable
signal FAN_TACH_TARGET: std_logic :='0'; --!
signal FAN_TACH_DIV2_INT: std_logic :='0';

signal slot_probe_dly: std_logic_vector(1 downto 0);
signal slot_sense_ctr: slv8_array( 1 downto 0);

signal dna_dout: std_logic;
signal dna_read: std_logic :='1'; -- First clock is a read
signal dna_shift: std_logic := '1'; -- Will start shifting as soon as read is disabled
signal dna_ctr: unsigned(5 downto 0) := to_unsigned(57-1, 6); -- Will shift 57 times

signal firmware_crc32: std_logic_vector(31 downto 0);

signal fpga_serial_number: std_logic_vector(56 downto 0) := (others=>'0'); -- Need to initialize because we do not shift all the 64 bits
signal target_fpga_serial_number: std_logic_vector(56 downto 0);

--signal target_local_subarray: std_logic_vector(1 downto 0);
--signal target_load_trigger: std_logic;
--signal target_load_trigger_dly: std_logic := '0';
--signal target_local_mac_addr: std_logic_vector(47 downto 0);
signal target_network_config_source: std_logic_vector(1 downto 0);
--signal target_local_base_ip_addr: std_logic_vector(31 downto 0);
--signal _base_ip_port: std_logic_vector(15 downto 0);

signal core_reg_wr_en: std_logic; -- indicates if the FPGA serial number matches the target serial number

signal bsb_core_din: std_logic_vector(7 downto 0);
signal bsb_core_dout: std_logic_vector(7 downto 0);
signal bsb_core_addr: std_logic_vector(6 downto 0); -- 5 bit word number (max 32 registers) + 2 bits (4 bytes per word)
signal bsb_core_wr_en: std_logic;
signal bsb_core_rd_en: std_logic;

-- Network parameters from the core registers
signal spi_fpga_local_ip_address: std_logic_vector(31 downto 0) := X"0A0A0A0B";
signal spi_fpga_local_ip_port: std_logic_vector(15 downto 0) := X"A028"; -- 41000
signal spi_fpga_local_mac_address: std_logic_vector(47 downto 0) := X"123456789ABC";
signal spi_fpga_ch0_remote_ip_port: std_logic_vector(15 downto 0);
signal spi_fpga_ch1_remote_ip_address: std_logic_vector(31 downto 0);
signal spi_fpga_ch1_remote_ip_port: std_logic_vector(15 downto 0);
signal spi_fpga_ch1_remote_mac_address: std_logic_vector(47 downto 0);

--signal udp_stack_reset: std_logic;
--signal ctrl_master_reset: std_logic;

-- signal local_mac_addr_int: std_logic_vector(47 downto 0);

-- Default Network settings -- Valid until new targets are loaded (requires the matching FPGA serial number in the TARGET_FPGA_SERIAN_NUMBER)
--signal local_base_ip_addr_reg: std_logic_vector(31 downto 0) := X"0A0A0A0B";
--signal local_base_ip_port_reg: std_logic_vector(15 downto 0) := X"A028"; -- 41000
--signal local_network_config_source_reg: std_logic_vector(1 downto 0) := sel(SIM, "11", "00"); -- Normally Use SPI-based networking parameters, but use default local parameters if this is simulated
--signal local_mac_addr_reg: std_logic_vector(47 downto 0) := X"123456789ABC";
--signal local_subarray_reg: std_logic_vector(1 downto 0) := "00";

-- signal udp_tx_frame_ctr: unsigned(7 downto 0) := (others=>'0');
-- signal udp_rx_frame_ctr: unsigned(7 downto 0) := (others=>'0');

-- Mux signals
signal user_mux_source: slv4_array(0 to 3);

-- IRIG-B receiver

signal irig_source: std_logic_vector(2 downto 0) := "000";
-- signal irigb_out_int: std_logic;
-- signal irig_vect : std_logic_vector(0 to 3);
signal ts: irigb; -- Current time as obtained by the IRIG-B decoder
signal pps_ctr: unsigned(5 downto 0);
signal pps_int: std_logic;

signal ts_sample: irigb; -- Sampled time
signal ts_sample_event_trig_in: std_logic; -- Automatically generated by the event counter trigger (on the event_ctr_clk). Toggled on every trigger event.
signal ts_sample_event_trig_out: std_logic; --

--signal event_ts_sample_trig_reg: std_logic; -- registers the trigger for the IRIGB time, from other clock domain. First stage of a synchronizer. Needs ASYNC_REG attribute.
--signal event_ts_sample_trig_reg2: std_logic; -- second stage of the IRIG-B sampling trigger synchronizer. Needs ASYNC_REG attribute.
--attribute ASYNC_REG of event_ts_sample_trig_reg: signal is "true";
--attribute ASYNC_REG of event_ts_sample_trig_reg2: signal is "true";
--signal event_ts_sample_trig_reg3: std_logic; -- Equals event_ts_sample_trig when the trigger has been processed.

signal ts_sample_refclk_trig_in: std_logic; -- Automatically generated by the event counter trigger (on the event_ctr_clk). Toggled on every trigger event.
signal ts_sample_refclk_trig_out: std_logic;
--signal refclk_ts_sample_trig_reg: std_logic; -- registers the trigger for the IRIGB time, from other clock domain. First stage of a synchronizer. Needs ASYNC_REG attribute.
--signal refclk_ts_sample_trig_reg2: std_logic; -- second stage of the IRIG-B sampling trigger synchronizer. Needs ASYNC_REG attribute.
--attribute ASYNC_REG of refclk_ts_sample_trig_reg: signal is "true";
--attribute ASYNC_REG of refclk_ts_sample_trig_reg2: signal is "true";
--signal refclk_ts_sample_trig_reg3: std_logic; -- Equals event_ts_sample_trig when the trigger has been processed.

signal ts_target: irigb; -- Target time used with the time comparator
signal ts_compare_enable: std_logic;
signal ts_force: std_logic;
signal ts_before_target: std_logic;

signal refclk_sample: unsigned(63 downto 0);

--signal target_refclk_count: unsigned(63 downto 0);
-- PWM signals
signal pwm_period: unsigned(31 downto 0);
signal pwm_high_time: unsigned(31 downto 0);
signal pwm_offset: unsigned(31 downto 0);
signal pwm_ctr: unsigned(31 downto 0);
signal pwm_active: std_logic;
signal pwm_out_int: std_logic;
signal pwm_soft_reset: std_logic;


-- Event counter and capture
signal event_sample: unsigned(47 downto 0); -- Captured value
signal event_ctr_soft_reset: std_logic;

signal manual_event_sample_trig: std_logic;

signal event_sample_done: std_logic;
attribute async_reg of event_sample_done: signal is "true";

-- Reference clock counter capture logic
signal manual_refclk_sample_trig: std_logic; -- indicates when to capture the reference counter
signal manual_refclk_sample_trig_reg: std_logic; -- 1st stage of the synchronizer
attribute ASYNC_REG of manual_refclk_sample_trig_reg: signal is "true";
signal manual_refclk_sample_trig_reg2: std_logic; -- delayed version used to detect the rising edge and do clock synchronization (needs ASYNC_REG)
attribute ASYNC_REG of manual_refclk_sample_trig_reg2: signal is "true";
signal manual_refclk_sample_trig_reg3: std_logic;
signal refclk_sample_done: std_logic;
attribute async_reg of refclk_sample_done: signal is "true";
signal ts_sample_trig10: std_logic :='0';
signal ts_sample_trig10_ack: std_logic;
signal ts_sample_done: std_logic;

-- External PLL
signal pll_sync_pre: std_logic;


signal ctrl_reset_trig: std_logic;

--signal bp_buck_sync_wr_dat: std_logic_vector(31 downto 0);
--signal bp_buck_sync_rd_dat: std_logic_vector(31 downto 0);
--signal bp_buck_sync_rd_dat_valid: std_logic;

--signal release_ctr_mon: std_logic_vector(7 downto 0);
--signal sync_ctr_mon: std_logic_vector(7 downto 0);
begin

-----------------------------------------------------------------------------------
-- CONTROL and STATUS Bytes
-----------------------------------------------------------------------------------
--! \addtogroup memory_map
--! GPIO Module
--!
--!  -------------------------------------------------------------------
--! |  Page   | Addr|Bit(s)|     Name                    | Description |
--! |---------|-----|------|-----------------------------|-------------|
--! | CONTROL |  0  |  7   | CTRL_FLAG_GLOBAL_TRIG       | |
--! |         |     |  6   | CTRL_FLAG_BUCK_SYNC_ENABLE  | Enables the generation of the Buck switcher synchronization signals. If '0', all sync lines are held low to let the switcher free-run.|
--! |         |     |  5   | CHAN_CLK_RESET              | Resets the MMCM that generates the channelizer clocks |
--! |         |     |  4   | CHAN_CLK_SOURCE             | Selects the source of the channelizer clocks: 0: ADC clock, 1: 200 MHz system clock. CHAN_CLK_RESET or ADCDAQ_RESET must be asserted when doing the change to allow the MMCM to lock properly to the new clock.|
--! |         |     |  3   | ADCDAQ_RESET                | Resets all ADCDAQ modules. This also resets the channelizer clock MMCM, the channelizers and the correlators.|
--! |         |     |  2   | (unused)                    | |
--! |         |     | 1:0  | ADC_RESET                   | ADC RESET line (active High) for each FMC ADC boards (bit 0 is for ADC board 0, etc) |
--! |         |  1  | 7:0  | CTRL_FLAG_BUCK_CLK_DIV      | System clock frequency divider ratio used to set the buck sync frequency|
--! |         |  2  |  7   | LCD_E                       | LCD Enable |
--! |         |     |  6   | LCD_RS                      | LCD Command/Data flag|
--! |         |     |  5   | LCD_RW                      | LCD Read/Write flag|
--! |         |     |  4   | (unused)                    | |
--! |         |     | 3:0  | LCD_DB                      | LCD data bus (4 bits) |
--! |         |  3  |  7   | BLINKER_RESET               | |
--! |         |     |  6   | CHAN_RESET_ASYNC            | Resets all channelizers |
--! |         |     |  5   | CORR_RESET_ASYNC            | Resets all correlators |
--! |         |     | 4:0  | (unused)                    | |
--! |         |  4  | 7:5  | (unused)                    | |
--! |         |     | 4:0  | HOST_FRAME_READ_RATE        | Indicates how often the host reads its UDP buffers in order to throttle the Ethernet output data rate. The read period is 2*(2^HOST_FRAME_READ_RATE)*(1/ctrl_clk) where CTRL lk is 125 MHz|
--! |         |5-12 | 63:0 | BUCK_PHASE                  | Phase of each of the 16 Buck sync lines. There are 16 possible phase values for each line. Bits 3:0 is for phase 0, bits 7:4 for phase 1 etc.|
--! |         |13-24|      | (unused)                    | |
--! |         |25-32| 63:57| (unused)                    | |
--! |         |     | 56:0 | TARGET_FPGA_DNA             | Target FPGA serial number: The core registers can be written via BSB commands if this target serial number matches the actual serial number of the FPGA |
--! |         |  33 |      | (unused)                    | |
--! |         |34-37| 31:0 | pwm_offset                  | Number of events (frames) to delay before starting to generate the first High of the PWM output|
--! |         |38-41| 31:0 | pwm_high_time               | Number of events (frames) to keep the PWM output at High|
--! |         |42-45| 31:0 | pwm_period                  | Number of events (frames) between PWM High (i.e PWM period)|
--! |         |  33 | 7    | pwm_soft_reset              | Software reset of the PWM module. Active high. |
--! |         |     | 7:3  | (unused)                    | |
--! |         |     | 2:0  | user_mux_source             | Selects which user source to send to the user output. |
--! | STATUS  |  0  |  7   | USER_DATA_VALID             | is '1' when the ACCESS0 register data (firmware timestamp) is valid |
--! |         |     | 6:0  | COOKIE                      | Defined as a GENERIC (default = 0x42)|
--! |         |  1  | 7:0  | LOG2_FRAME_LENGTH           | |
--! |         |  2  | 7:0  | NUMBER_OF_CHANNELIZERS      | Number of antennas processing pipelines implemented in the firmware |
--! |         |  3  | 7:0  | NUMBER_OF_CORRELATORS       | Number of correlators implemented in the firmware |
--! |         |  4  | 7:0  | NUMBER_OF_CHANNELIZERS_TO_CORRELATE | Number of antennas connected to the correlators. Only antennas 0 to N-1 will be connected. This sets the numbe rof parallel multipliers and accumulators in the correlator. |
--! |         |  5  | 7:0  | NUMBER_OF_CHANNELIZERS_WITH_FFT   | Indicates how many channelizers have a FFT module. Those will be channeizers 0 to N-1|
--! |         |  6  | 7:0  | NUMBER_OF_GPU_LINKS         | Indicates how GPU Links are implemented. If zero, the GPU module is not present at all (not even the common registers)|
--! |         | 7-10| 31:0 | firmware_timestamp          | 32-bit word containing the timestamp of the firmware inserted during the bitgen process |
--! |         | 11  | 7:0  | PLATFORM_ID                 | Type of platform on which the firmware is running. 0=ML605, 1=KC705, 3=MGK7MB, 4=ZCU111 |
--! |         |12-19| 63:57| (unused)                    | |
--! |         |     | 56:0 | FPGA_DNA                    | FPGA unique serial number |
--! |         | 20  | 7:0  | NUMBER_OF_CROSSBAR_INPUTS   | Indicates how many channelizers are connected to the crossbar inputs. Those will be channeizers 0 to N-1|
--! |         | 21  | 7:0  | NUMBER_OF_CROSSBAR1_OUTPUTS | Indicates the number of crossbar1 outputs. Those outputs feed the GPU links and the FPGA correlators (if implemented).
--! |         |22-23| 15:0 | PROTOCOL_VERSION            | 16-bit value indicating the protocol version. A change in the version means that some change is needed on host control software. |
--! |         | 24  | 7:0  | CHANNELIZERS_CLOCK_SOURCE   | ADC channel from which the channelizer clocks are derived. Useful to know if we should expect the clock to be missing and use alternate internal clock.
--! |         |25-30|      | (unused)                    | |
--! |         |  31 | 7:0  | slot_sense_ctr(0)           | |
--! |         |  32 | 7:0  | slot_sense_ctr(1)           | |
--! |         |  33 | 7:6  | adc_pll_lock                | |
--! |         |     | 5:2  | (unused)                    | |
--! |         |     |  1   | udp_tx_overflow             | |
--! |         |     |  0   | udp_rx_overflow             | |
--! |         |  34 | 7:0  | cmd_packet_counter          | |
--! |         |  35 | 7:0  | rply_packet_counter         | |
--! |         |  36 | 7:0  | NUMBER_OF_BP_SHUFFLE_LINKS  | |
--! |         |  37 |  7   | (unused)                    | |
--! |         |  37 |  7   | bp_gpio_int_in              | |
--! |         |  37 |  6   | bp_gpio_int_in              | |
--! |         |  37 |  5   | gpio_irq_in                 | |
--! |         |  37 |  4   | flash_cs_in                 | |
--! |         |  37 |  3   | uart_tx_in                  | |
--! |         |  37 |  2   | uart_rx_in                  | |
--! |         |  37 |  1   | gpio_rst_in                 | |
--! |         |  37 |  0   | arm_irq_in                  | |
--! ------------------------------------------------------------------------------
--!



-- CONTROL Byte 0: Buco converter sync enable, channelizer clock source, various resets
CTRL_FLAG_GLOBAL_TRIG      <= CONTROL_BYTES(0)(7);
CTRL_FLAG_BUCK_SYNC_ENABLE <= CONTROL_BYTES(0)(6);
CHAN_CLK_RESET_ASYNC       <= CONTROL_BYTES(0)(5);
CHAN_CLK_SOURCE            <= CONTROL_BYTES(0)(4);
ADCDAQ_RESET_ASYNC         <= CONTROL_BYTES(0)(3);
ADC_RST                    <= reverse_bits_and_dir(CONTROL_BYTES(0)(NUMBER_OF_ADC_BOARDS-1 downto 0));


-- CONTROL Byte 1: Buck converter switching frequency control
CTRL_FLAG_BUCK_CLK_DIV <= UNSIGNED(CONTROL_BYTES(1));

-- CONTROL Byte 2: LCD control
lcd_gen: if IMPLEMENT_LCD generate
	LCD_E  <= CONTROL_BYTES(2)(7);
	LCD_RS <= CONTROL_BYTES(2)(6);
	LCD_RW <= CONTROL_BYTES(2)(5);
	LCD_DB <= CONTROL_BYTES(2)(3 downto 0);
else generate-- make sure the outputs are driven while the associated CTRL_SLAVE logic is synthesized out
	LCD_E  <= '0';
	LCD_RS <= '0';
	LCD_RW <= '0';
	LCD_DB <= (others => '0');
end generate;

-- CONTROL Byte 3: Various reset and clock selection controls
USER_RESET <='0';
BLINKER_RESET       <= CONTROL_BYTES(3)(7);
CHAN_RESET_ASYNC    <= CONTROL_BYTES(3)(6);
CORR_RESET_ASYNC    <= CONTROL_BYTES(3)(5);
ctrl_reset_trig     <= CONTROL_BYTES(3)(4);
sysmon_user_reset   <= CONTROL_BYTES(3)(3);
clk10_sel           <= CONTROL_BYTES(3)(2);
pll_sync_pre        <= CONTROL_BYTES(3)(1);
--USER_RESET <= CONTROL_BYTES(3)(0);

-- CONTROL Byte 4: UDP data throttling control
HOST_FRAME_READ_RATE    <= CONTROL_BYTES(4)(4 downto 0);

gen_sw_sync: if IMPLEMENT_SWITCHER_SYNC generate
-- CONTROL bytes 5-12: Buck converter phases (8 phases)
BUCK_PHASE <= to_slv(CONTROL_BYTES(5 to 12));
end generate;

-- CONTROL bytes 13: ADC calibration freeze control
adc_cal_freeze <= reverse_bits_and_dir(CONTROL_BYTES(13));

-- CONTROL bytes 14-24: Unused

-- CONTROL bytes 25-32: Target serial number
target_fpga_serial_number(56) <= CONTROL_BYTES(25)(0);
target_fpga_serial_number(55 downto 0) <= to_slv(CONTROL_BYTES(26 to 32));

-- CONTROL byte 33: serial-based core register write control
target_network_config_source <= CONTROL_BYTES(33)(3 downto 2); --"00": core reg write always enabled; "01", "10" or "11": core reg write only when target serial matches the FPGA's serial



-- CONTROL byte 34-37, 38-41, 42-45
pwm_offset <= to_unsigned(CONTROL_BYTES(34 to 37));
pwm_high_time <= to_unsigned(CONTROL_BYTES(38 to 41));
pwm_period <= to_unsigned(CONTROL_BYTES(42 to 45));

-- CONTROL byte 46: PWM reset, IO for QC tests, user output mux control
pwm_soft_reset <= CONTROL_BYTES(46)(7);
bp_gpio_int_oe <= CONTROL_BYTES(46)(4);
user_mux_source(0) <= CONTROL_BYTES(46)(3 downto 0);

-- CONTROL byte 47: IO's for QC tests
uart_tx_oe   <= CONTROL_BYTES(47)(7);
uart_tx_out  <= CONTROL_BYTES(47)(6);
uart_rx_oe   <= CONTROL_BYTES(47)(5);
uart_rx_out  <= CONTROL_BYTES(47)(4);
gpio_rst_oe  <= CONTROL_BYTES(47)(3);
arm_irq_out  <= CONTROL_BYTES(47)(0);
gpio_rst_out <= CONTROL_BYTES(47)(2);
arm_irq_oe   <= CONTROL_BYTES(47)(1);

-- CONTROL byte 48 -- User output mux control, various IO's for QC tests
user_mux_source(3) <= CONTROL_BYTES(48)(7 downto 4);
gpio_irq_oe        <= CONTROL_BYTES(48)(3);
gpio_irq_out       <= CONTROL_BYTES(48)(2);
flash_cs_oe        <= CONTROL_BYTES(48)(1);
flash_cs_out       <= CONTROL_BYTES(48)(0);


-- CONTROL byte 49 -- User output 1 & 2 mux control
user_mux_source(2) <= CONTROL_BYTES(49)(7 downto 4);
user_mux_source(1) <= CONTROL_BYTES(49)(3 downto 0);

-- CONTROL byte 50 -- User bits, IRIG-B delay control
user_bit(1)       <= CONTROL_BYTES(50)(7);
user_bit(0)       <= CONTROL_BYTES(50)(6);
irigb_delay_reset <= CONTROL_BYTES(50)(5);
irigb_delay       <= CONTROL_BYTES(50)(4 downto 0);

-- STATUS Byte 0
STATUS_BYTES(0)(7)          <= USER_DATA_VALID;
STATUS_BYTES(0)(6 downto 0) <= to_slv(COOKIE, 7);

-- STATUS Byte 1 - ADC data frame geometry
STATUS_BYTES(1)(4 downto 0) <= to_slv(LOG2_SAMPLES_PER_FRAME, 5); -- 16384=14
STATUS_BYTES(1)(7 downto 5) <= to_slv(LOG2_SAMPLES_PER_WORD, 3); -- 2: 4 samples/word, 3: 8 samples/word

-- STATUS Byte 2
STATUS_BYTES(2) <= to_slv(NUMBER_OF_CHANNELIZERS, 8);


-- STATUS Byte 3
STATUS_BYTES(3) <= to_slv(NUMBER_OF_CORRELATORS,8);

--STATUS_BYTES(3)(7 downto 4) <= (others=>'0');

--STATUS Byte 4-6
STATUS_BYTES(4) <= to_slv(NUMBER_OF_CHANNELIZERS_TO_CORRELATE, 8);
STATUS_BYTES(5) <= to_slv(NUMBER_OF_CHANNELIZERS_WITH_FFT,8);
STATUS_BYTES(6) <= to_slv(NUMBER_OF_GPU_LINKS,8);

-- STATUS Bytes 7-10
STATUS_BYTES(7 to 10) <= to_slv8_array(firmware_timestamp);  -- ** ToDo: still used by Python, but redundant with core regs.

-- STATUS Bytes 11: Platform ID
STATUS_BYTES(11) <= to_slv(PLATFORM_ID, 8);

-- STATUS Bytes 12-19: FPGA serial number
STATUS_BYTES(12)(7 downto 1) <= (others=>'0');
STATUS_BYTES(12)(0) <= fpga_serial_number(56);
STATUS_BYTES(13 to 19) <= to_slv8_array(fpga_serial_number(55 downto 0));

STATUS_BYTES(20) <= to_slv(NUMBER_OF_CROSSBAR_INPUTS, 8);
STATUS_BYTES(21) <= to_slv(NUMBER_OF_CROSSBAR1_OUTPUTS, 8);

STATUS_BYTES(22 to 23) <= to_slv8_array(to_slv(PROTOCOL_VERSION, 16));
STATUS_BYTES(24) <= to_slv(CHANNELIZERS_CLOCK_SOURCE, 8);
-- Connect signals to module ports

-- STATUS Bytes 25
STATUS_BYTES(25) <= to_slv(NUMBER_OF_ADCS, 8);

-- STATUS Bytes 26
STATUS_BYTES(26) <= to_slv(ADC_BITS_PER_SAMPLE, 8);

-- STATUS Bytes 27: ADC calibration frozen flags (for 8 ADCs)
STATUS_BYTES(27)  <= reverse_bits_and_dir(adc_cal_frozen);

-- STATUS Bytes 28: ADC calibration signal detect flags (for 8 ADCs)
STATUS_BYTES(28)  <= reverse_bits_and_dir(adc_cal_signal_detect);

-- STATUS Bytes 29-30
STATUS_BYTES(29 to 30) <= (others => (others => '0'));

-- STATUS Bytes 31-32
STATUS_BYTES(31) <= slot_sense_ctr(0); -- is this still used?
STATUS_BYTES(32) <= slot_sense_ctr(1);

-- STATUS Bytes 33-35
STATUS_BYTES(33)(7 downto 8-NUMBER_OF_ADC_BOARDS) <= reverse_bits_and_dir(adc_pll_lock);
STATUS_BYTES(33)(5 downto 2) <= (others=>'0');
--STATUS_BYTES(33)(1) <= udp_tx_overflow;
--STATUS_BYTES(33)(0) <= udp_rx_overflow;

STATUS_BYTES(34) <= cmd_packet_counter;
STATUS_BYTES(35) <= rply_packet_counter;

STATUS_BYTES(36) <= to_slv(NUMBER_OF_BP_SHUFFLE_LINKS, 8);
-- STATUS_BYTES(36)(1) <= bp_shuffle_lock(1);

--ADC_RST<=CTRL_FLAG_ADC_RESET;

--CLK<=ADC_CLK; -- select clock to use for Buck SYNC generation

STATUS_BYTES(37)(0) <= arm_irq_in;
STATUS_BYTES(37)(1) <= gpio_rst_in;
STATUS_BYTES(37)(2) <= uart_rx_in;
STATUS_BYTES(37)(3) <= uart_tx_in;
STATUS_BYTES(37)(4) <= flash_cs_in;
STATUS_BYTES(37)(5) <= gpio_irq_in;
STATUS_BYTES(37)(6) <= bp_gpio_int_in;
STATUS_BYTES(37)(7) <= core_reg_wr_en; -- debug


-----------------------------------------------------------------------------------
-- Memory-Mapped interface
-----------------------------------------------------------------------------------
--! Instantiates a memory-mapped interface to the control and status bytes
CTRL_SLAVE0: entity work.CTRL_SLAVE
	GENERIC MAP (
		NUMBER_OF_CONTROL_BYTES => CONTROL_BYTES'Length(1), -- Length of array in the first dimension: number of bytes
		NUMBER_OF_STATUS_BYTES => STATUS_BYTES'Length(1),
		DEFAULT_CONTROL_BYTES => ('0' & to_std_logic(BUCK_SYNC_ENABLE) & "010000" & -- Byte 0
			                      to_slv(BUCK_CLK_DIVIDE_FACTOR,8) & -- Byte 1
			                      X"00" & -- Byte 2: LCD
			                      X"60" & -- Byte 3: Reset and clock control
			                      X"14" & -- Byte 4: HOST_FRAME_READ_RATE
			                      X"FEDCBA9876543210" & -- Bytes 5-12: Buck sync phases
			                      X"00" & -- Byte 13: ADC cal freeze
			                      X"0000000000_00000000_A028" & -- Bytes 14-24: Unused
			                      X"0000000000000000" & -- Bytes 25-32: Target FPGA ID
			                      X"00" & --Byte 33: Core reg write mode
			                      X"00000000_0002faf0_0005f5e1" & -- Bytes 34-45: PWM offset/high time/period
			                      X"00_00_00" &
			                      X"89" & -- Byte 49 -- User output 1 & 2 mux control
			                      X"00"), -- Byte 50: User bits, IRIG-B delay control
        RAM_DATA_WIDTH          => 8, -- 8 or 16 bits
        RAM_ADDR_WIDTH          => 5+2,  -- 6 bits (32 register words) + 2 bits (4 bytes per word)
        RAM_LATENCY             => 1
	)
	PORT MAP(
		-- Control interface (command and reply stream buses)
		ctrl_cmd_in_dat => ctrl_cmd_in_dat,
		ctrl_cmd_in_rdy => ctrl_cmd_in_rdy,
		ctrl_rply_out_dat => ctrl_rply_out_dat,
		ctrl_rply_out_rdy => ctrl_rply_out_rdy,
		ctrl_clk => ctrl_clk,
		ctrl_rst => ctrl_rst,

		CONTROL_BYTES => CONTROL_BYTES,
		STATUS_BYTES => STATUS_BYTES,

        RAM_DIN   => bsb_core_din,
        RAM_DOUT  => bsb_core_dout,
        RAM_ADDR  => bsb_core_addr,
        RAM_WR_EN => bsb_core_wr_en,
        RAM_RD_EN => bsb_core_rd_en
	);


-- ctrl_reset pulse generator
-----------------------------
-- Generates a long pulse on ctrl_reset_pulse when a low-to-high transition is seen on ctrl_reset_trig.
-- Operates on ctrl_clk.
ctrl_reset_blk: block
	signal ctrl_reset_trig_reg: std_logic;
	signal ctrl_reset_ctr: unsigned(3 downto 0);
begin
	ctrl_reset_proc: process(ctrl_clk)
	begin
		if rising_edge(ctrl_clk) then
			ctrl_reset_trig_reg <= ctrl_reset_trig;

			if signed(ctrl_reset_ctr) = -1 then
				ctrl_reset_pulse <= '0';
			else
				ctrl_reset_ctr <= ctrl_reset_ctr + 1;
			end if;

			if ctrl_reset_trig='1' and ctrl_reset_trig_reg='0' then
				ctrl_reset_pulse <= '1';
				ctrl_reset_ctr <= (others => '0');
			end if;

		end if; --clk
	end process;
end block;

gen_armspi: if IMPLEMENT_ARM_SPI generate
	arm_spi0: entity work.arm_spi port map (
		-- SPI interface
		sck => arm_spi_sck,
		miso => arm_spi_miso,
		mosi => arm_spi_mosi,
		cs_n => arm_spi_cs_n,

		-- Master bus interface
		addr => spi_addr,
		din  => spi_rdat,
		dout => spi_wdat,
		rreq => spi_rreq,
		rack => spi_rack,
		wreq => spi_wreq,
		wack => spi_wack,

		clk => ctrl_clk,
		reset => '0' -- redundant; cs_n does the same thing

	);
end generate;



-------------------------
-- Core Register assignments
-------------------------
-- Register write values

-- Register Read values
-- Registers 0-2
core_reg_rd_value(0) <= x"beefface"; -- (Read only) Core firmware cookie
core_reg_rd_value(1) <= to_slv(COOKIE, 32); -- (Read only) Application firmware cookie
core_reg_rd_value(2) <= X"00000000"; -- (Read only) Application Flags: Kintex 7

-- Register 3
core_reg_rd_value(3) <= firmware_crc32; -- (Read/Write with readback) Firmware CRC32, computed by the host application and stored here for future reference
firmware_crc32       <= core_reg_wr_value(3);

-- Registers 4-6
core_reg_rd_value(4) <= firmware_timestamp; -- (Read only) Firmware timestamp, taken from the USER_ACCESS data filled in when the bitstream file was generated
core_reg_rd_value(5) <= fpga_serial_number(31 downto 0); -- (Read only)
core_reg_rd_value(6) <= "0000000" & fpga_serial_number(56 downto 32); -- (Read only)

-------------------------
-- Application-specific registers
-------------------------

-- Networking configuration -- Local Rx MAC/IP/PORT numbers
------------------------------------------------------------
-- Register 7 - FPGA Network interface MAC address
core_reg_rd_value(7)                     <= spi_fpga_local_mac_address(31 downto 0); -- (Read/Write with readback)
spi_fpga_local_mac_address(31 downto 0)  <= core_reg_wr_value(7);

-- Register 8 - FPGA Network interface MAC address and listening command port
core_reg_rd_value(8)                     <= spi_fpga_local_mac_address(47 downto 32) & spi_fpga_local_ip_port; -- (Read/Write with readback)
spi_fpga_local_mac_address(47 downto 32) <= core_reg_wr_value(8)(31 downto 16);
spi_fpga_local_ip_port                   <= core_reg_wr_value(8)(15 downto 0);
-- Register 9  - FPGA Network interface IP address
core_reg_rd_value(9)                     <= spi_fpga_local_ip_address; -- (Read/Write with readback)
spi_fpga_local_ip_address                <= core_reg_wr_value(9);

-- IRIG-B timestamp registers
-------------------------
-- Register 10 (_IRIGB_SAMPLE0_ADDR)
core_reg_rd_value(10)(31 downto 26) <= to_slv(pps_ctr); -- (Read only)
core_reg_rd_value(10)(25 downto 8)  <= ts_sample.sbs; -- (Read only)
core_reg_rd_value(10)(7 downto 0)   <= to_slv(ts_sample.y); -- (Read only)
-- Register 11 (_IRIGB_SAMPLE1_ADDR)
core_reg_rd_value(11)(31 downto 30) <= to_slv(ts_sample.source(1 downto 0)); -- (Read only)
core_reg_rd_value(11)(29)           <= ts_sample.recent; -- (Read only)
core_reg_rd_value(11)(28 downto 20) <= to_slv(ts_sample.d); -- (Read only)
core_reg_rd_value(11)(19 downto 14) <= to_slv(ts_sample.h); -- (Read only)
core_reg_rd_value(11)(13 downto 7)  <= to_slv(ts_sample.m); -- (Read only)
core_reg_rd_value(11)(6 downto 0)   <= to_slv(ts_sample.s); -- (Read only)
-- Register 12 (_IRIGB_SAMPLE2_ADDR)
core_reg_rd_value(12)(31 downto 30) <= irig_source(1 downto 0); -- (Read/Write with readback)
core_reg_rd_value(12)(29)           <= manual_refclk_sample_trig; -- (Read/Write with readback)
core_reg_rd_value(12)(28)           <= manual_event_sample_trig; -- (Read/Write with readback)
core_reg_rd_value(12)(27 downto 0)  <= to_slv(ts_sample.ss); -- (Read only)
irig_source(1 downto 0)             <= core_reg_wr_value(12)(31 downto 30);
manual_refclk_sample_trig           <= core_reg_wr_value(12)(29);
manual_event_sample_trig            <= core_reg_wr_value(12)(28);
-- Register 13 (_IRIGB_TARGET0_ADDR)
core_reg_rd_value(13)(31)          <= irig_source(2); -- (Read/Write with readback)
core_reg_rd_value(13)(7 downto 0)  <= core_reg_wr_value(13)(7 downto 0); -- (Readback)
ts_target.y                        <= unsigned(core_reg_wr_value(13)(7 downto 0));
irig_source(2)                     <= core_reg_wr_value(13)(31);
-- Register 14 (_IRIGB_TARGET1_ADDR)
core_reg_rd_value(14)(31)          <= ts_before_target; -- (Read-only)
core_reg_rd_value(14)(30)          <= event_sample_done; -- (Read only)
core_reg_rd_value(14)(29)          <= refclk_sample_done; -- (Read-only)
core_reg_rd_value(14)(28 downto 0) <= core_reg_wr_value(14)(28 downto 0); -- (Readback)
ts_target.d                        <= unsigned(core_reg_wr_value(14)(28 downto 20));
ts_target.h                        <= unsigned(core_reg_wr_value(14)(19 downto 14));
ts_target.m                        <= unsigned(core_reg_wr_value(14)(13 downto 7));
ts_target.s                        <= unsigned(core_reg_wr_value(14)(6 downto 0));
-- Register 15 (_IRIGB_TARGET2_ADDR)
core_reg_rd_value(15)(31)          <= ts_compare_enable; -- (Readback)
core_reg_rd_value(15)(30)          <= ts_force; -- (Readback)
core_reg_rd_value(15)(27 downto 0) <= core_reg_wr_value(15)(27 downto 0); -- (Readback)
ts_target.ss                       <= unsigned(core_reg_wr_value(15)(27 downto 0));
-- (make sure the rest of ts_target is driven to prevent warnings)
ts_target.c <= (others=>'0');
ts_target.sbs <= (others=>'0');
ts_target.recent <= '0';
ts_target.source <= (others=>'0');

ts_compare_enable                  <= core_reg_wr_value(15)(31);
ts_force                           <= core_reg_wr_value(15)(30);
-- Register 16 (_IRIGB_EVENT_CTR_ADDR)
core_reg_rd_value(16) <= std_logic_vector(event_sample(31 downto 0)); -- (Read-only)

-- Registers 17 (_IRIGB_EVENT_CTR_ADDR2)
core_reg_rd_value(17)(15 downto 0) <= std_logic_vector(event_sample(47 downto 32)); -- (read-only)
core_reg_rd_value(17)(31 downto 16) <= (others=>'0'); -- (read-only)

--core_reg_rd_value(17)(31 downto 16) <= bp_buck_sync_wr_dat(31 downto 16); -- readback
--core_reg_rd_value(17)(15 downto 8)  <= release_ctr_mon; --unused
--core_reg_rd_value(17)(7 downto 0)   <= sync_ctr_mon; --unused

-- Registers 18 (_SFP_CONFIG_ADDR)

sfp_config_vector                   <= core_reg_wr_value(18); -- read-write
core_reg_rd_value(18)               <= core_reg_wr_value(18); -- (Readback)

-- Register 19 (_SFP_STATUS_ADDR)
core_reg_rd_value(19)(31 downto 18) <= core_reg_wr_value(19)(31 downto 18); -- (readback)
core_reg_rd_value(19)(17)           <= udp_tx_overflow; -- (Read only)
core_reg_rd_value(19)(16)           <= udp_rx_overflow; -- (Read only)
core_reg_rd_value(19)(15 downto 0)  <= sfp_status_vector; -- (Read-only)
udp_stack_reset                     <= core_reg_wr_value(19)(31);
ctrl_master_reset                   <= core_reg_wr_value(19)(30);

-- Register 20 (_REMOTE_IP_PORT_ADDR) - FPGA command reply port
spi_fpga_ch0_remote_ip_port         <= core_reg_wr_value(20)(15 downto 0);
core_reg_rd_value(20)(15 downto 0)  <= spi_fpga_ch0_remote_ip_port; -- (Readback)

-- Register 21 (_IRIGB_REFCLK_SAMPLE)
core_reg_rd_value(21)             <= std_logic_vector(refclk_sample(31 downto 0)); -- read
--target_refclk_count(31 downto 0)  <= unsigned(core_reg_wr_value(21));

-- Register 22 (_IRIGB_REFCLK_SAMPLE2)
core_reg_rd_value(22)             <= std_logic_vector(refclk_sample(63 downto 32)); -- read
--target_refclk_count(63 downto 32) <= unsigned(core_reg_wr_value(21));

-- Data Channel networking parameters

-- Register 23 - Data packet destination MAC address
core_reg_rd_value(23)               <= spi_fpga_ch1_remote_mac_address(31 downto 0); -- (Read/Write with readback)
spi_fpga_ch1_remote_mac_address(31 downto 0)  <= core_reg_wr_value(23);
-- Register 24 - Data packet destination MAC address and destination port
core_reg_rd_value(24)               <= spi_fpga_ch1_remote_mac_address(47 downto 32) & spi_fpga_ch1_remote_ip_port; -- (Read/Write with readback)
spi_fpga_ch1_remote_mac_address(47 downto 32) <= core_reg_wr_value(24)(31 downto 16);
spi_fpga_ch1_remote_ip_port                   <= core_reg_wr_value(24)(15 downto 0);
-- Register 25 - Data packet destination IP address
core_reg_rd_value(25)               <= spi_fpga_ch1_remote_ip_address; -- (Read/Write with readback)
spi_fpga_ch1_remote_ip_address           <= core_reg_wr_value(25);

core_regs0: entity work.register_array
	generic map(
		ADDRESS_MASK => X"000000" & "------XX",
		NUMBER_OF_REGISTERS => NUMBER_OF_CORE_REGISTERS,
		DEFAULT_REGISTER_VALUES => core_reg_default_values,
		ADDRESS_WIDTH => 32,
		SIM => False --! Indicates this is running as a simulation. Used to accelerate simulations
	)
	port map (
		-- Control interface (*** JFC: to be replaced by an AXI4-Lite bus)
		s_addr => spi_addr,
		s_wdat => spi_wdat,
		s_rdat => spi_rdat,
		s_wreq => spi_wreq,
		s_wack => spi_wack,
		s_rreq => spi_rreq,
		s_rack => spi_rack,


		-- Simplified byte r/w interface
		din => bsb_core_din,
		dout => bsb_core_dout,
		addr => bsb_core_addr,
		wr_en => bsb_core_wr_en and core_reg_wr_en, -- write only if we match the serial number
		rd_en => bsb_core_rd_en,

		-- Register interface
		reg_wr_value  => core_reg_wr_value,
		reg_rd_value  => core_reg_rd_value,

		clk => ctrl_clk -- Clocks both control and register interface
	);

-----------------------
-- IRIG-B decoder
-----------------------
-- irig_vect <=  sync_in & time_in & '0' & '0'; -- Combine all irig signal source in a single vector

irigb_decoder0 : entity work.irigb_decoder
	port map (
		clk_200mhz => clk200,
		irig       => irigb_mux_in,
		source     => unsigned(irig_source),
		pps        => pps_int,
		ts         => ts
	);

irigb_before_target <= ts_before_target;
irigb_comparator0: entity work.irigb_comparator
	port map (
		current_ts    => ts,
		target_ts     => ts_target,
		compare_en    => ts_compare_enable,
		force_sync         => ts_force,
		before_target => ts_before_target, -- Is '1' when current time is before the target time, and '0' when it is equal of after. There is 7 clocks latency compared to current time input.
		clk_200mhz    => clk200
	);

irigb_encoder0: entity work.irigb_encoder
	port map (
		clk_200mhz => clk200,
		ts_out => irigb_out
	);


irigb_pps <= pps_int;
-----------------------
-- IRIG-B Time capture
-----------------------
--
-- This process is used to capture the IRIG-B time and count the PPS pulses.
-- IRIG-B capture is triggered either by capturing the reference clock counter
-- or by capturing the event/frame event.
--
-- `event_ts_sample_trig` is handled by the event/frame capture logic, which operates
-- on on the event_ctr_clk (chan_clk(0), 200 MHz derived from the ADC or
-- multi-phase PLL).
--
--
-- ts_sample_trig10 is handled by the refclk counter capture logic, which is
-- clocked on clk10.
--
-- This process operates in the clk200 clock domain. Ultimately all the
-- trigger clocks are derived from clk10, but they have an unknown phase. So
-- he have to deal with clock domain crossing on the trigger.
--
-- Triggering is done by inverting the state of `event_ts_sample_trig` or
-- `ts_sample_trig10`. The capture is done when  the signal differ from the
-- correspnding acknowledge bit. The acknowledge bit is then set to the
-- trigger signal to indicate that the caapture is done.
--
-- Note that the acknowledge signals are on clk200, not on the clock of their
-- corresponding trigger.
--
irigb_capture_blk: block

	signal ts_sample_refclk_trig_in_resync: std_logic;
	signal ts_sample_event_trig_in_resync: std_logic;
	signal pps_int_dly: std_logic;

begin

	-- Synchronize the trigger signal from the 10 MHz manual/refclk trigger to the clk200 irigb clock
	refclk_trig_cdc0: xpm_cdc_single
		generic map (SRC_INPUT_REG => 0)
		port map (src_clk => '0', src_in => ts_sample_refclk_trig_in, dest_clk => clk200, dest_out => ts_sample_refclk_trig_in_resync);


	-- Synchronize the trigger signal from the frame/event clock to the clk200 irigb clock
	event_trig_cdc0: xpm_cdc_single
		generic map (SRC_INPUT_REG => 0)
		port map (src_clk => '0', src_in => ts_sample_event_trig_in, dest_clk => clk200, dest_out => ts_sample_event_trig_in_resync);

	irigb_ctr_proc: process(clk200)
		begin
			if rising_edge(clk200) then

				-- Count the pps pulses on the rising edge of the PPS signal. This
				-- is used mainly for debugging. This counter is never resetted.
				pps_int_dly <= pps_int;

				if pps_int='1' and pps_int_dly='0' then
					pps_ctr <= pps_ctr + 1;
				end if;

				-- Sample the IRIG-B timestamp when the event or refclk triggers change state
				ts_sample_event_trig_out <= ts_sample_event_trig_in_resync;
				ts_sample_refclk_trig_out <= ts_sample_refclk_trig_in_resync;
				if ts_sample_event_trig_in_resync /= ts_sample_event_trig_out or
				   ts_sample_refclk_trig_in_resync /= ts_sample_refclk_trig_out then
					ts_sample <= ts; -- register the current IRIG-B time
				end if;

			end if;  -- if clk200
		end process;
end block;

--------------------------------
-- Event (frame) counter capture
--------------------------------
--! On the rising edge of manual_event_sample_trig, we arm the trigger. When the end
--! of frame is detected, we enable the sampling to capture the frame counter
--! and the timestamp on the first sample of the nest frame. The capture is
--! also enabled after reset so we capture the time of the first word of the
--! first frame after reset.
--!
--! Typically:
--!    event_ctr_en <= axis_adc_tvalid(0);
--!    event_ctr_inc <= axis_adc_tlast(0);
--
event_capture_blk: block

	signal event_ctr: unsigned(47 downto 0);

	signal ts_sample_event_trig_out_resync: std_logic;
	signal manual_event_sample_trig_dly: std_logic;
	signal event_sample_done_int: std_logic;
	signal event_sample_en: std_logic;
	signal event_sample_arm: std_logic;

begin

	-- Synchronize the trigger signal from the 10 MHz manual/refclk trigger to the clk200 irigb clock
	ts_trig_cdc0: xpm_cdc_single
		generic map (SRC_INPUT_REG => 0)
		port map (src_clk => '0', src_in => ts_sample_event_trig_out, dest_clk => event_ctr_clk, dest_out => ts_sample_event_trig_out_resync);


	event_proc: process(event_ctr_clk)
	begin
		if rising_edge(event_ctr_clk) then

			-- Capture the event info
			if event_ctr_en = '1' then -- when tvalid=1
				-- Count events
				if event_ctr_inc = '1' then
					event_ctr <= event_ctr + 1;
				end if;
				-- Sample event
				event_sample_en <= '0'; -- Single clock pulse. Overriden below.
				if event_sample_en = '1' then
					event_sample <= event_ctr;
					event_sample_done_int <= '1';
					ts_sample_event_trig_in <= not ts_sample_event_trig_in; -- cause a transition to indicate that the timestamp should be sampled now
				end if;
			end if;


			if manual_event_sample_trig='0' then
				event_sample_done_int <= '0';
			end if;

			event_sample_done <= to_std_logic(event_sample_done_int='1' and ts_sample_event_trig_in = ts_sample_event_trig_out_resync);

			-- Arm the sampling at the rising edge of manual_event_sample_trig
			manual_event_sample_trig_dly <= manual_event_sample_trig;
			if manual_event_sample_trig='1' and manual_event_sample_trig_dly='0' then
				event_sample_arm <= '1';
			elsif event_sample_arm = '1' and event_ctr_en = '1' and event_ctr_inc='1' then
				event_sample_arm <= '0';
				event_sample_en <= '1';
			end if;

			if event_ctr_reset='1' or event_ctr_soft_reset='1' then
				event_ctr <= (others=>'0');
				event_sample_arm <= '0';
				event_sample_en <= '1'; -- sample the first incoming frame after reset
			end if;
		end if; --CLK
	end process;
end block;
--------------------------------------
-- 10 MHz reference clock time capture
--------------------------------------
-- Count the reference clock cycles and capture the current count on the
-- rising edge of `manual_refclk_sample_trig`. A reference counter capture also
-- automaatically triggers the IRIB-time capture.
--
-- The 10 MHz clock cycles in a free-running counter. This is our
-- internal time reference, independent from the data frames, and is not
-- affected by sync. The 10 MHz clock might come from a maser, and is not
-- necessarily perfectly aligned to the IRIG-B time that is sent by the GPS.
--
-- The process also capture the current reference clock counter and IRIG-B
-- when a rising edge is seen on `manual_refclk_sample_trig`. `refclk_sample_done`
-- will go high (on the clk10 clock) when the IRIG-B has finished sampling
-- both the counter AND the IRIG-B (sampling the counter is instantaneous so
-- we don`t have to worry about synchronizing this one). Note that this does
-- not guarantee that the IRIG-B is valid, just that the timestamp was
-- registered properly and is stable and ready for reading. You have to check
-- the timestamp flags to check if the time was updated lately.
--
-- To be clear: the capture is done at any time - it is not synchronized to a frame/event.
--
-- The IRIG-B sampling happens a few clocks after the counte capture due to the synchronization regitering.
-- This can be used to obtain a correspondance between the maser time (as
-- represented by the reference counter) and the GPS time (as obtained by the
-- IRIG-B capture)
--


refclk_capture_blk: block
	signal manual_refclk_sample_trig_resync: std_logic;
	signal manual_refclk_sample_trig_dly: std_logic;
	signal ts_sample_refclk_trig_out_resync: std_logic;
	signal refclk_ctr: unsigned(63 downto 0);

begin


	-- Synchronize the manual trigger signal to the 10 MHz clock
	man_trig_cdc0: xpm_cdc_single
		generic map (SRC_INPUT_REG => 0)
		port map (src_clk => '0', src_in => manual_refclk_sample_trig, dest_clk => clk10, dest_out => manual_refclk_sample_trig_resync);
	-- Synchronize the trigger feedback signal to the 10 MHz clock
	ts_trig_cdc0: xpm_cdc_single
		generic map (SRC_INPUT_REG => 0)
		port map (src_clk => '0', src_in => ts_sample_refclk_trig_out, dest_clk => clk10, dest_out => ts_sample_refclk_trig_out_resync);

	refclk_capture_proc: process(clk10)
		begin
			if rising_edge(clk10) then
				-- Count the 10 MHz clocks continuously
				refclk_ctr <= refclk_ctr + 1;

				-- detect the target condition
				-- refclk_sync_trig <= to_std_logic(refclk_ctr = target_refclk_count);

				-- Capture the counter value on the rising edge of `manual_refclk_sample_trig`.
				-- Manual trigger (edge sensitive, as it is driven by a slow process)
				-- This automatically triggers capture of the IRIG-B time (about 2xclk200 later)`
				--manual_refclk_sample_trig_reg <= manual_refclk_sample_trig; -- two stage synchronizer
				--manual_refclk_sample_trig_reg2 <= manual_refclk_sample_trig_reg;
				manual_refclk_sample_trig_dly <= manual_refclk_sample_trig_resync;
				if manual_refclk_sample_trig_resync='1' and manual_refclk_sample_trig_dly='0' then
					refclk_sample <= refclk_ctr; -- register the current counter
					ts_sample_refclk_trig_in <= not ts_sample_refclk_trig_in; -- triggers the sampling of the IRIG-B time
					refclk_sample_done <= '0';
				else
					refclk_sample_done <= to_std_logic(ts_sample_refclk_trig_in = ts_sample_refclk_trig_out_resync);
				end if;
				-- Event-based trigger (sync or start of frame) (level-sensitive)
				--event_refclk_sample_trig_reg <= event_refclk_sample_trig; -- two stage synchronizer
				--event_refclk_sample_trig_reg2 <= event_refclk_sample_trig_reg;
				--event_refclk_sample_trig_ack <= event_refclk_sample_trig_reg2; --
				--if event_refclk_sample_trig_reg2 /= event_refclk_sample_trig_ack then
				--	refclk_sample <= refclk_ctr; -- register the current counter
				--end if;
			end if; --CLK
		end process;
end block;


-- PLL sync
pll_sync <= pll_sync_pre;

--! User muxed output selection
user_gen: for i in 0 to 3 generate
	user_mux_out(i) <= user_mux_in(to_integer(unsigned(user_mux_source(i))));
	user_mux_oe(i) <= '0' when signed(user_mux_source(i)) = -1 else '1';
end generate;

--! Implement USR_ACCESS for VIRTEX6-based platforms
USRACCESS_V6: if FPGA_SERIES=FPGA_VIRTEX6 generate
	USR_ACCESS0: USR_ACCESS_VIRTEX6
		port map(
			CFGCLK    => open,--1-bit Configuration Clock output
			DATA      => firmware_timestamp,--32-bit Configuration Data output
			DATAVALID => USER_DATA_VALID--1-bit Active high data validoutput
			);
end generate;

--! Implement USR_ACCESS for 7-series platforms

USRACCESS_7: if FPGA_SERIES=FPGA_KINTEX7 or FPGA_SERIES=FPGA_ULTRASCALEPLUS generate
	USR_ACCESS0: USR_ACCESSE2
		port map(
			CFGCLK    => open, --1-bit Configuration Clock output
			DATA      => firmware_timestamp, --32-bit Configuration Data output
			DATAVALID => USER_DATA_VALID --1-bit Active high data validoutput
			);
end generate;

gen_dna7: if FPGA_SERIES=FPGA_KINTEX7 generate
	dna0 : DNA_PORT
		generic map (
			SIM_DNA_VALUE => X"000000000000000" -- Specifies a sample 57-bit DNA value for simulation
		)
		port map (
			DOUT => dna_dout, -- 1-bit output: DNA output data.
			CLK => dna_clk, -- 1-bit input: Clock input.
			DIN => '0', -- 1-bit input: User data input pin.
			READ => dna_read, -- 1-bit input: Active high load DNA, active low read input.
			SHIFT => dna_shift -- 1-bit input: Active high shift enable input.
		);
	end generate;

gen_dnaup: if FPGA_SERIES=FPGA_ULTRASCALEPLUS generate
	-- The core currently reads only 57 bits
	dna0 : DNA_PORTE2
		port map (
			DOUT => dna_dout, -- 1-bit output: DNA output data.
			CLK => dna_clk, -- 1-bit input: Clock input.
			DIN => '0', -- 1-bit input: User data input pin.
			READ => dna_read, -- 1-bit input: Active high load DNA, active low read input.
			SHIFT => dna_shift -- 1-bit input: Active high shift enable input.
		);
end generate;


-- Read the 57-bit DNA
dna_proc: process(dna_clk)
	begin
		if rising_edge(dna_clk) then
			dna_read <= '0';
			if dna_read= '0' and dna_shift='1' then -- when data is ready and we have not finished shifting
				fpga_serial_number <= std_logic_vector(shift_left(unsigned(fpga_serial_number), 1));
				fpga_serial_number(0) <= dna_dout;
				dna_ctr <= dna_ctr - 1;
				if dna_ctr = 0 then
					dna_shift <= '0';
				end if;
			end if;
		end if;
	end process;


-- comm_mon_proc: process(ctrl_clk)
-- 	begin
-- 		if rising_edge(ctrl_clk) then
-- 			if udp_rx_frame='1' then
-- 				udp_rx_frame_ctr <= udp_rx_frame_ctr + 1;
-- 			end if;
-- 			if udp_tx_frame='1' then
-- 				udp_tx_frame_ctr <= udp_tx_frame_ctr + 1;
-- 			end if;
-- 		end if;
-- 	end process;

network_setup_proc: process(ctrl_clk)
	begin
		if rising_edge(ctrl_clk) then
			-- Set core_reg_wr_en to conditionally enable writing to the core registers.
			-- When target_network_config_source="00", core register writes are always allowed.
			-- When target_network_config_source/="00", core register writes are allowed only if the target FPGA serial number matches the actual FPGA serial number.
			-- This feature allows the networking parameters of one specific board to be configured by
			--   1) broadcast a write command to configure the target board FPGA serial number and set target_network_config_source to "01"
            --   2) broadcast write commands to set the networking parameters; only the target board will accept the configuration
			-- The serial number of all FPGAs on the network can be obtain through a broadcast read command. Further board information (board model, serial number, slot number etc) can be obtained from GPIO and I2C acceses.
			-- This provides a simple way to setup the networking parameters of the FPGAs without requiring an on-board network-enabled processor.

			core_reg_wr_en <= to_std_logic(fpga_serial_number = target_fpga_serial_number or target_network_config_source="00");


			-- FPGA network interface addresses
			local_mac_addr     <= spi_fpga_local_mac_address;
			local_base_ip_addr <= spi_fpga_local_ip_address;
			local_subarray     <= (others=>'0');

			-- Control Channel(UDP Channel 0) parameters
			local_base_ip_port <= spi_fpga_local_ip_port; -- command listening port
			-- Command reply IP and MAC: hardwired to be the same as the the source addres of the previous incoming command packets
			remote_ip_port0  <= spi_fpga_ch0_remote_ip_port; -- command reply destination port

			-- Data Channel (UDP Channel 1) parameters
			remote_ip_addr1     <= spi_fpga_ch1_remote_ip_address; -- Data packet destination IP addres
			remote_mac_addr1    <= spi_fpga_ch1_remote_mac_address; -- Data packets destination MAC address
			remote_ip_port1     <= spi_fpga_ch1_remote_ip_port; -- Data packets destination port

		end if;
	end process;

TRIG_ASYNC<=CTRL_FLAG_GLOBAL_TRIG;


gen_sw_sync_proc: if IMPLEMENT_SWITCHER_SYNC generate
--! Generates the buck switching regulator synchronization signal
buckproc: process(clk200)
	begin
		if rising_edge(clk200) then
			if ctrl_flag_buck_sync_enable='0' then
					clk_ctr <= (0=>'1', others=>'0');
					buck_phase_ctr <= (others=>'0');
					buck_sync <= (others=>'0'); -- Make sure both phases are not driving the Bucks after reset and until we enable the buck sync
			else
				if (clk_ctr = CTRL_FLAG_BUCK_CLK_DIV) then
					clk_ctr <= (0=>'1', others=>'0');
					buck_phase_ctr <= buck_phase_ctr + 1;
				else
					clk_ctr <= clk_ctr + 1;
				end if;

				for i in 0 to NUMBER_OF_BUCK_SYNC_LINES-1 loop
					if unsigned(BUCK_PHASE(4*i+3 downto 4*i)) = buck_phase_ctr then
						buck_sync(i) <='1';
					elsif unsigned(BUCK_PHASE(4*i+3 downto 4*i)) = buck_phase_ctr + 8 then -- wraps around
						buck_sync(i) <='0';
					end if;
				end loop;
			end if; -- RST
		end if; -- CLK

	end process;
end generate;


gen_fan: if IMPLEMENT_FAN generate
------ Fan process  ------------------
--! Debounce the fan tachometer signal
--! Implements the ML605 Tachometer readout with debouncing and provides a logic signal toggling at half the fan rotation frequency.
--! The tachometer signal pulses twices a revolution, but each pulse is very noisy.
--! This process implements some basic debouncing so we can read the rotation speed correctly using the general frequency counter
--!
--! There is no RST clause since this is reset as soon as the first chang eof tachymeter value is encountered, which is needed anyways for an accurate frequency count.
fanproc: process(clk200)
	begin
		if rising_edge(clk200) then
			if FAN_TACH/=FAN_TACH_TARGET then
				FAN_TACH_CTR<=(others=>'0');
			elsif SIGNED(FAN_TACH_CTR)=-1 then -- if we reach the end of the counter without encountering a change in the signal state
				FAN_TACH_TARGET<= not FAN_TACH_TARGET; -- toggle the target bit. The loop will now look for that target to be stable
				FAN_TACH_CTR<=(others=>'0');
				if FAN_TACH_TARGET='1' then -- generate a divide by 2 frequency signal to be used by the frequency counter
					FAN_TACH_DIV2_INT<=not FAN_TACH_DIV2_INT;
				end if;
			else
				FAN_TACH_CTR<=FAN_TACH_CTR+1;
			end if;
		end if; --CLK
	end process;

FAN_TACH_DIV2<=FAN_TACH_DIV2_INT;
FAN_PWM <='1'; -- Fan is always operating at 100% speed
end generate;


slotproc: process(ctrl_clk)
	begin
		if rising_edge(ctrl_clk) then
			slot_probe_dly <= slot_probe;
			for i in 0 to 1 loop
				if slot_probe_dly(i)='0' and slot_probe(i)='1' then
					slot_sense_ctr(i) <= (others=>'0');
				elsif slot_probe(i)='1' and slot_sense(i)='0' and signed(slot_sense_ctr(i))/=-1 then
					slot_sense_ctr(i) <= std_logic_vector(unsigned(slot_sense_ctr(i)) + 1);
				end if;
			end loop;
		end if; --CLK
	end process;


------ PWM generator process  ------------------
pwm_out <= pwm_out_int;
pwm_proc: process(pwm_clk)
	begin
		if rising_edge(pwm_clk) then
			if pwm_ctr_en='1' then
				pwm_ctr <= pwm_ctr + 1;
				if pwm_active='0' then
					if pwm_ctr = pwm_offset then
						pwm_active <= '1';
						pwm_ctr <= (others => '0');
						pwm_out_int <= '1';
					end if;
				else
					if pwm_ctr = pwm_high_time then
						pwm_out_int <= '0';
					elsif pwm_ctr = pwm_period then
						pwm_ctr <= (others => '0');
						pwm_out_int <= '1';
					end if;
				end if;
			end if; -- if ctr_en
			-- Synchronous Reset
			if pwm_reset='1' or pwm_soft_reset='1'then
				pwm_active <= '0';
				pwm_ctr <= (others=>'0');
				pwm_out_int <= '0';
			end if;
		end if; --CLK
	end process;

----------------------------------------------------------------
-- Backplane BUCK SYNC generator and backplane access arbitrator
----------------------------------------------------------------
-- This was an experiment to see if we boards in a crate could collaborate to
-- generate a single clock to which all boards would be synchronized. This was
-- done by borrowing the clock-slowing principle of multiple I2C devices
-- connected on the same bus.
--
--	In addition, to this we modulated the clock to transmit data across multiple boards.
--
-- This is not used, and causes implementaton to fail on ZCU111, so we remove it.
--
--bp_buck_sync0: entity work.bp_buck_sync
--	port map (
--		sync => bp_buck_sync,
--		sync_mon => bp_buck_sync_mon,

--		-- Data interface
--		--release_ctr_mon => release_ctr_mon,
--		--sync_ctr_mon => sync_ctr_mon,
--		wr_dat => bp_buck_sync_wr_dat,
--		rd_dat => bp_buck_sync_rd_dat,
--		rd_dat_valid => bp_buck_sync_rd_dat_valid,
--		clk10 => clk10,
--		rst => bp_buck_sync_wr_dat(31)
--	);

end Behavioral;

