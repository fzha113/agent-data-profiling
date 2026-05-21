from dataclasses import dataclass


MAX_SELECTED_TAGS = 4
DEFAULT_TAGS: tuple[str, ...] = ()


@dataclass(frozen=True)
class TagMetadata:
    """
    Metadata for a geothermal station raw PI tag exposed by the profiling app.

    Args:
        name: Raw table column name.
        display_name: Human-readable label for controls and charts.
        unit: Unit text if curated; empty string when not configured.
        process_area: Process area if curated; empty string when not configured.
        description: Description if curated; empty string when not configured.
        related_tags: Related raw tag names for later agent analysis.
        kg_node_id: Knowledge graph node identifier for later agent analysis.
    """

    name: str
    display_name: str
    unit: str
    process_area: str
    description: str
    related_tags: tuple[str, ...] = ()
    kg_node_id: str | None = None


def _metadata(name: str) -> TagMetadata:
    return TagMetadata(
        name=name,
        display_name=name.replace("_", " "),
        unit="",
        process_area="",
        description="",
    )


_CATALOG_TAGS = (
    "Hp_Seperator_Pressure_1",
    "Hp_Steam_Flow_To_Turbine",
    "Hp_Brine_Flow",
    "Lp_Seperator_Pressure_1",
    "Lp_Steam_Flow_To_Turbine",
    "Gross_Generator_Output",
    "Parasitic_Load",
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
    "Cooling_Tower_Fan_A_Current",
    "Cooling_Tower_Fan_B_Current",
    "Cooling_Tower_Fan_C_Current",
    "Cooling_Tower_Fan_D_Current",
    "Cooling_Tower_Fan_E_Current",
    "Cooling_Tower_Fan_F_Current",
    "Cooling_Tower_Fan_G_Current",
    "Cooling_Tower_Fan_H_Current",
    "Cooling_Tower_Fan_I_Current",
    "Cooling_Tower_Fan_J_Current",
    "Cooling_Tower_Inlet_Condensate_Temperature",
    "Generator_Cooling_Air_Temperature_Cold_Turbine_Side",
    "1st_Brip_A_Motor_Speed",
    "1st_Brip_B_Motor_Speed",
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
)

TAG_CATALOG: dict[str, TagMetadata] = {tag: _metadata(tag) for tag in _CATALOG_TAGS}


def get_catalog_tags() -> tuple[str, ...]:
    """
    Return the ordered app catalog tag names.

    Args:
        None.

    Returns:
        tuple[str, ...]: Ordered raw tag column names available for profiling.
    """
    return tuple(TAG_CATALOG)


def validate_selected_tags(tags: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """
    Validate a user-selected tag list against the app catalog.

    Args:
        tags: User-selected raw tag column names.

    Returns:
        tuple[str, ...]: Validated tag names in the original order.

    Raises:
        ValueError: If the selection is empty, too large, or includes unknown tags.
    """
    selected_tags = tuple(tags)
    if not selected_tags:
        raise ValueError("Select at least one tag.")
    if len(selected_tags) > MAX_SELECTED_TAGS:
        raise ValueError(f"Select no more than {MAX_SELECTED_TAGS} tags.")

    unknown_tags = [tag for tag in selected_tags if tag not in TAG_CATALOG]
    if unknown_tags:
        raise ValueError(f"Unknown tag selection: {', '.join(unknown_tags)}")

    return selected_tags
