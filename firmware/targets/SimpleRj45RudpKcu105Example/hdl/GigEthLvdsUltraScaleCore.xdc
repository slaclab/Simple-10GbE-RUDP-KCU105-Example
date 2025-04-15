##############################################################################
## This file is part of 'Simple-10GbE-RUDP-KCU105-Example'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Simple-10GbE-RUDP-KCU105-Example', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *core_resets_i/rst_dly_reg*}] -filter {REF_PIN_NAME =~ PRE}]
set_property CLOCK_DELAY_GROUP cdg0 [get_nets -of [get_pins -of [get_cells -hierarchical -filter {NAME =~ *core_clocking_i/clk312_buf}] -filter {REF_PIN_NAME =~ O}]]
set_property CLOCK_DELAY_GROUP cdg0 [get_nets -of [get_pins -of [get_cells -hierarchical -filter {NAME =~ *core_clocking_i/clk625_buf}] -filter {REF_PIN_NAME =~ O}]]

# false path constraints to async inputs coming directly to synchronizer
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *SYNC_*/data_sync*}] -filter {REF_PIN_NAME =~ D}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *SYNC_*/reset_sync*}] -filter {REF_PIN_NAME =~ PRE}]

set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ */lvds_transceiver_mw/serdes_10_to_1_ser8_i/gb0/*_dom_ch_reg}] -filter {REF_PIN_NAME =~ D}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ */lvds_transceiver_mw/serdes_1_to_10_ser8_i/rxclk_r_reg}] -filter {REF_PIN_NAME =~ D}]

set_false_path -from [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/gb0/loop2[*].ram_ins*/RAM*}] -filter {REF_PIN_NAME =~ CLK}] -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/gb0/loop0[*].dataout_reg[*]}] -filter {REF_PIN_NAME =~ D}]
set_false_path -from [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_10_to_1_ser8_i/gb0/loop2[*].ram_ins*/RAM*}] -filter {REF_PIN_NAME =~ CLK}] -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_10_to_1_ser8_i/gb0/loop0[*].dataout_reg[*]}] -filter {REF_PIN_NAME =~ D}]
set_false_path -from [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/gb0/loop2[*].ram_ins*/RAM*}] -filter {REF_PIN_NAME =~ CLK}] -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/rxdh*}] -filter {REF_PIN_NAME =~ D}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/iserdes_m}] -filter {REF_PIN_NAME =~ RST}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/iserdes_s}] -filter {REF_PIN_NAME =~ RST}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_10_to_1_ser8_i/oserdes_m}] -filter {REF_PIN_NAME =~ RST}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *sync_speed_10*/data_sync*}] -filter {REF_PIN_NAME =~ D}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *gen_sync_reset/reset_sync*}] -filter {REF_PIN_NAME =~ PRE}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *reset_sync_inter*/*sync*}] -filter {REF_PIN_NAME =~ PRE}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *reset_sync_output_cl*/*sync*}] -filter {REF_PIN_NAME =~ PRE}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *reset_sync_rxclk_div*/*sync*}] -filter {REF_PIN_NAME =~ PRE}]
set_false_path -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *reset_rxclk_div*/*sync*}] -filter {REF_PIN_NAME =~ PRE}]

set_false_path -from [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_10_to_1_ser8_i/gb0/read_enable_reg}] -filter {REF_PIN_NAME =~ C}] -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_10_to_1_ser8_i/gb0/read_enable_dom_ch_reg}] -filter {REF_PIN_NAME =~ D}]
set_false_path -from [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/gb0/read_enable_reg}] -filter {REF_PIN_NAME =~ C}] -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ *lvds_transceiver_mw/serdes_1_to_10_ser8_i/gb0/read_enabler_reg}] -filter {REF_PIN_NAME =~ D}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-1} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-1 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */gb*/loop2[*].ram_inst*/RAM*}] -filter {name =~ *CLK}]\
 -to [get_pins -of [get_cells -hier -filter {name =~ */gb*/loop0[*].dataout_reg[*]*}] -filter {name =~ *D}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-10} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-10 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */gb*/loop2[*].ram_inst*/RAM*}] -filter {name =~ *CLK}]\
 -to [get_pins -of [get_cells -hier -filter {name =~ */gb*/loop0[*].dataout_reg[*]*}] -filter {name =~ *D}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-2} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-2 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hierarchical -filter {NAME =~ */gb*/loop2[*].ram_ins*/RAM*}] -filter {name =~ *CLK}]\
 -to [get_pins -of [get_cells -hierarchical -filter {NAME =~ */gb*/loop0[*].dataout_reg[*]*}] -filter {name =~ *D}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-10} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-10 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */gpcs_pma_inst/USE_ROCKET_IO.RX_RST_SM_TXOUTCLK.MGT_RX_RESET_INT_reg*}] -filter {name =~ *C}]\
 -to [get_pins -of [get_cells -hier -filter {name =~ */reset_sync1*}] -filter {name =~ *PRE}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-11} -user "gig_ethernet_pcs_pma" -desc "The CDC-11 warning is waived as this is within the LVDS_transiver module and safe to ignore" -tags "11999"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */gpcs_pma_inst/USE_ROCKET_IO.RX_RST_SM_TXOUTCLK.MGT_RX_RESET_INT_reg*}] -filter {name =~ *C}]\
 -to [get_pins -of [get_cells -hier -filter {name =~ */reset_sync1*}] -filter {name =~ *PRE}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-10} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-10 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */reset_wtd_timer/reset_reg*}] -filter {name =~ *C}]\
 -to [get_pins -of [get_cells -hier -filter {name =~ */reset_sync1*}] -filter {name =~ *PRE}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-11} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-11 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */reset_wtd_timer/reset_reg*}] -filter {name =~ *C}]\
 -to [get_pins -of [get_cells -hier -filter {name =~ */reset_sync1*}] -filter {name =~ *PRE}]

create_waiver -internal -scope -quiet -type CDC -id {CDC-1} -user "gig_ethernet_pcs_pma" -tags "11999" -desc "The CDC-1 warning is waived as this is within the LVDS_transiver module and safe to ignore"\
 -from [get_pins -of [get_cells -hier -filter {name =~ */gb*/read_enable_reg*}] -filter {name =~ *C}]\
 -to [list [get_pins -of [get_cells -hier -filter {name =~ */gb*/read_enabler_reg*}] -filter {name =~ *D}] [get_pins -of [get_cells -hier -filter {name =~ */gb*/read_enable_dom_ch_reg*}] -filter {name =~ *D}] ]

