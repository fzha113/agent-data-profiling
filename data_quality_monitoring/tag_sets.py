RULE_TAGS = {
    "KAG": {
        "stuck_value": [
            "Hp_Seperator_Pressure_1",
            "Hp_Steam_Flow_To_Turbine",
            "HP_BRINE_FLOW",
            "Lp_Seperator_Pressure_1",
            "Lp_Steam_Flow_To_Turbine",
            "Gross_Generator_Output",
            "PARASITIC_LOAD",
            "Condenser_Pressure_A",
            "Condenser_Pressure_B",
            "Condenser_Pressure_C",
            "Condenser_Pressure_D",
            "Humidity",
            "Atmospheric_Temperature_Dry",
            "Cooling_Water_Flow",
            "Vacuum_Pump_40_Current",
            "Vacuum_Pump_60_Current",
            "Vacuum_Pump_80_Current",
            "COOLING_TOWER_FAN_A_CURRENT",
            "COOLING_TOWER_FAN_B_CURRENT",
            "COOLING_TOWER_FAN_C_CURRENT",
            "COOLING_TOWER_FAN_D_CURRENT",
            "COOLING_TOWER_FAN_E_CURRENT",
            "COOLING_TOWER_FAN_F_CURRENT",
            "COOLING_TOWER_FAN_G_CURRENT",
            "COOLING_TOWER_FAN_H_CURRENT",
            "COOLING_TOWER_FAN_I_CURRENT",
            "COOLING_TOWER_FAN_J_CURRENT",
            "Cooling_Tower_Inlet_Condensate_Temperature",
            "1ST_BRIP_A_MOTOR_SPEED",
            "1ST_BRIP_B_MOTOR_SPEED",
            "2nd_Stage_Brip_A_Current",
            "2nd_Stage_Brip_B_Current",
            "Main_Cooling_Water_Temperature",
            "Stg_Cooling_Water_Supply_Pressure",
            "KA61_Prod_Well_Two_Phase_Flow",
            "Turbine_Hp_Chamber_Pressure",
            "Turbine_Lp_Chamber_Pressure",
            "Total_Turbine_Steam_Flow",
            "Condenser_Hotwell_Temperature",
            "Kgl_To_Tp_Rtu_Mw_Net",
            "Net_Power",
            "Kawerau_Total_Mw",
            "Station_Enthalpy",
            "LP_STEAM_PRESSURE_2",
        ],
        "outlier": [
            "Hp_Seperator_Pressure_1",
            "Hp_Steam_Flow_To_Turbine",
            "HP_BRINE_FLOW",
            "Lp_Seperator_Pressure_1",
            "Lp_Steam_Flow_To_Turbine",
            "Gross_Generator_Output",
            "PARASITIC_LOAD",
            "Condenser_Pressure_A",
            "Condenser_Pressure_B",
            "Condenser_Pressure_C",
            "Condenser_Pressure_D",
            "Humidity",
            "Atmospheric_Temperature_Dry",
            "Cooling_Water_Flow",
            "Vacuum_Pump_40_Current",
            "Vacuum_Pump_60_Current",
            "Vacuum_Pump_80_Current",
            "COOLING_TOWER_FAN_A_CURRENT",
            "COOLING_TOWER_FAN_B_CURRENT",
            "COOLING_TOWER_FAN_C_CURRENT",
            "COOLING_TOWER_FAN_D_CURRENT",
            "COOLING_TOWER_FAN_E_CURRENT",
            "COOLING_TOWER_FAN_F_CURRENT",
            "COOLING_TOWER_FAN_G_CURRENT",
            "COOLING_TOWER_FAN_H_CURRENT",
            "COOLING_TOWER_FAN_I_CURRENT",
            "COOLING_TOWER_FAN_J_CURRENT",
            "Cooling_Tower_Inlet_Condensate_Temperature",
            "Generator_Cooling_Air_Temperature_Cold_Turbine_Side",
            "1ST_BRIP_A_MOTOR_SPEED",
            "1ST_BRIP_B_MOTOR_SPEED",
            "2nd_Stage_Brip_A_Current",
            "2nd_Stage_Brip_B_Current",
            "Main_Cooling_Water_Temperature",
            "Stg_Cooling_Water_Supply_Pressure",
            "KA61_Prod_Well_Two_Phase_Flow",
            "Turbine_Hp_Chamber_Pressure",
            "Turbine_Lp_Chamber_Pressure",
            "Total_Turbine_Steam_Flow",
            "Condenser_Hotwell_Temperature",
            "Kgl_To_Tp_Rtu_Mw_Net",
            "Net_Power",
            "Kawerau_Total_Mw",
            "Station_Enthalpy",
            "LP_STEAM_PRESSURE_2",
        ],
    }
}


def get_rule_tags(station: str, rule_type: str) -> list[str]:
    """
    Get the configured tags for a monitoring rule.

    Args:
        station: Station identifier.
        rule_type: Monitoring rule identifier.

    Returns:
        list[str]: Tags monitored by the rule.

    Raises:
        ValueError: If the station or rule type has no configured tag set.
    """
    if station not in RULE_TAGS:
        raise ValueError(f"Station does not define tags: {station}")

    station_tags = RULE_TAGS[station]
    if rule_type not in station_tags:
        raise ValueError(f"Rule type does not define tags for station {station}: {rule_type}")

    return list(station_tags[rule_type])
