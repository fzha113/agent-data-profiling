# KAG Station Process Context

This context is for KAG PI streaming data profiling and data quality incident analysis. Use it to interpret supplied tag statistics and incident windows. Do not treat this context as evidence that an event happened in the analysed time window. The supplied JSON data remains the evidence source.

## Station Objective

KAG is a geothermal station. Two-phase geothermal fluid from production wells is separated into steam and brine. Steam is sent through HP and LP turbine stages to generate gross MW. Parasitic load is then subtracted to produce net power. Brine and condensate are reinjected.

The station model and downstream dashboards use PI streaming data to estimate gross output, net output, two-phase flow, steam flows, condenser behaviour, GES behaviour, parasitic load, and forecast/optimisation outputs. Bad PI data can affect feature engineering, station modelling, forecasting, Power BI dashboards, set point optimisation, and drift monitoring.

## Main Process Path

1. Production wells and branchlines supply two-phase fluid. Current project notes include PK6/PK7, KA41/KA42/KA45/KA46, KA52, KA61, and related branchlines such as Fletcher Ave, CHH, Putanaki, and KA61 Branchline.
2. Two-phase flow enters the HP separator. The HP separator splits fluid into HP steam and HP brine.
3. HP steam can go to the turbine and can also supply motive steam to the GES. HP steam is higher energy than LP steam and is prioritised when turbine steam capacity is constrained.
4. HP brine passes to the LP separator. The LP separator flashes part of this into LP steam and leaves LP brine.
5. LP steam and HP turbine exhaust feed LP turbine sections. Total turbine steam flow is the combined steam through the turbine path.
6. Turbine exhaust enters the condenser. Condenser performance affects turbine back pressure and therefore output.
7. Condensate and cooling water circulate through the cooling tower. Cooling tower performance depends on inlet/outlet water temperature, cooling water flow, fan operation, ambient temperature, humidity, wind, and wet bulb temperature.
8. GES extracts non-condensable gas from the condenser using motive steam and vacuum pumps. GES behaviour can affect condenser pressure, motive steam use, parasitic load, and net output.
9. Brine from separators and some condensate are reinjected. Reinjection pump and BRIP behaviour can affect parasitic load and station constraints.

## Operating Limits And Investigation Anchors

Use these as process context only; use incident thresholds from supplied JSON when available.

- 2-phase intake has pipeline and consent constraints. Project notes mention 2810 t/h pipeline context and 2700 t/h plus NTGA consent context.
- HP steam pressure operating context is about 10.3 to 12.6 barg.
- LP steam pressure operating context is about 1.2 to 1.77 barg in optimiser limits.
- HP turbine steam flow context is about 186 to 540 t/h; optimiser max is about 540 t/h.
- LP steam flow optimiser max is about 266 t/h.
- Total turbine steam flow physical context is about 786 t/h; optimiser limit is about 784 t/h to avoid pushing to alarm/manual operation.
- Reinjection flow context includes a max around 2016 t/h in operating limit notes.
- HP brine flow can be high and is a key corrosion/erosion concern. Project notes say some actual ranges have been around 2000 to 2600 t/h, while a design reference was lower.
- Condenser pressure design context is about 0.08 to 0.13 bara. Cooling water notes say output can remain near maximum until condenser pressure is above about 0.09 bara, but this relationship depends on filtering and operating mode.
- Gross generator output nameplate context is about 113.67 MW.

## Feature Calculations

These calculations are used in KAG station model, steam flow calibration, or cross-validation work. Use them to suggest related checks, not to invent missing values.

- `HP_TURBINE_STEAM_FLOW = HP_STEAM_FLOW_ALL - HP_GES_STEAM_SUPPLY`
- `HP_turbine_steam_flow_calculated = C_stodola_coef_hp * sqrt(p_in_bara^2 - p_out_bara^2)`
  - `C_stodola_coef_hp` project value: median of last 8 months, about 44.18 in the calibration notes.
  - `p_in_bara` is derived from `Turbine_Hp_Chamber_Pressure`.
  - `p_out_bara` is derived from `Turbine_Lp_Chamber_Pressure`.
- `GES_calculated = HP_STEAM_FLOW_ALL - HP_turbine_steam_flow_calculated`
- `Total_turbine_steam_flow_calculated = C_stodola_coef_lp * sqrt(p_in_bara^2 - p_out_bara^2)`
  - `C_stodola_coef_lp` project value: about 355.45 in the calibration notes.
  - `p_in_bara` is derived from `Turbine_Lp_Chamber_Pressure`.
  - `p_out_bara` is derived from `Condenser_Pressure_A`.
- `LP_turbine_steam_flow_calculated = Total_turbine_steam_flow_calculated - HP_turbine_steam_flow_calculated`
- `HP_brine_flow_calculated` is derived from LP turbine steam flow and LP separator quality in the calibration notes.
- `Two_phase_flow = HP_STEAM_FLOW_ALL + HP_brine_flow_calculated` in the calibrated station model context.
- Steam table or CoolProp calculations use pressure, temperature, quality, enthalpy, and entropy to derive water/steam properties. The project uses CoolProp to model SteamTab behaviour.
- In separator physics, quality means steam fraction. HP separator and LP separator calculations use pressure, enthalpy, and quality to split flow into steam and brine. If calculation notes conflict with physical interpretation, call this out as a modelling-definition issue rather than treating it as a root cause.

## Two-Phase Flow Cross-Checks

The project compares several ways of estimating station two-phase flow to identify tag misalignment or process/model drift:

- `HP_VENTURI_STEAM_plus_HP_BRINE = HP_STEAM_FLOW_ALL + HP_BRINE_FLOW`
- `Sum_of_wells = steam flow of production wells + NTGA`, with low well flow values trimmed in the project notes.
- `HP_VENTURI_STEAM_plus_LP_BRINE_plus_LP_STEAM = HP_STEAM_FLOW_ALL + BRINE_FLOW_TO_REINJECTION + LP_STEAM_FLOW`
- `TOTAL_TURBINE_FLOW_plus_GES_plus_LP_BRINE = Total_Turbine_Steam_Flow + HP_GES_STEAM_SUPPLY + BRINE_FLOW_TO_REINJECTION`

If one flow tag drifts, investigate whether related flow calculations diverge at the same time.

## Tag To Process Mapping

Production wells and two-phase supply:
- `KA61_Prod_Well_Two_Phase_Flow`: KA61 production well two-phase flow.
- Other project tag lists include KA41, KA42, KA45, KA46, KA52, PK06, and PK07 two-phase flow tags, where available.
- `Station_Enthalpy`: station enthalpy context for energy content.

HP and LP separators:
- `Hp_Seperator_Pressure_1`: HP separator pressure, maps to station model HP steam pressure context.
- `Hp_Steam_Flow_To_Turbine`: HP steam flow to turbine context.
- `Hp_Brine_Flow`: HP brine flow context, important for two-phase estimates and brine/corrosion concerns.
- `Lp_Seperator_Pressure_1`: LP separator pressure context.
- `LP_STEAM_PRESSURE_2`: LP demister steam pressure context.
- `Lp_Steam_Flow_To_Turbine`: LP steam flow to turbine context.

Turbine and generator:
- `Turbine_Hp_Chamber_Pressure`: HP turbine chamber/nozzle pressure, used in HP Stodola calculation.
- `Turbine_Lp_Chamber_Pressure`: LP turbine chamber/nozzle pressure, used in HP and LP Stodola calculations.
- `Total_Turbine_Steam_Flow`: total turbine steam flow context.
- `Gross_Generator_Output`: gross MW output from the generator.
- `Net_Power`: net power after parasitic load.
- `Kgl_To_Tp_Rtu_Mw_Net` and `Kawerau_Total_Mw`: net/station MW context tags, depending on source definition.

Condenser, cooling tower, and ambient:
- `Condenser_Pressure_A`, `Condenser_Pressure_B`, `Condenser_Pressure_C`, `Condenser_Pressure_D`: condenser pressure points. `Condenser_Pressure_A` is used in LP Stodola flow calculation context.
- `Condenser_Hotwell_Temperature`: condenser hotwell temperature context.
- `Cooling_Water_Flow`: cooling water flow. Cooling water flow can be linked to condenser water level and hotwell pump control behaviour.
- `Main_Cooling_Water_Temperature`: main cooling water temperature.
- `Cooling_Tower_Inlet_Condensate_Temperature`: cooling tower inlet condensate temperature.
- `Cooling_Tower_Fan_A_Current` through `Cooling_Tower_Fan_J_Current`: fan current tags that indicate cooling tower fan operation/load.
- `Atmospheric_Temperature_Dry`: dry ambient temperature.
- `Humidity`: ambient humidity. Ambient temperature and humidity together affect wet bulb temperature and cooling performance.
- `Generator_Cooling_Air_Temperature_Cold_Turbine_Side`: generator cooling air temperature context.

GES, NCG, and parasitic load:
- `Vacuum_Pump_40_Current`, `Vacuum_Pump_60_Current`, `Vacuum_Pump_80_Current`: vacuum pump current tags for GES train behaviour.
- `Parasitic_Load`: parasitic load used to move from gross output to net output.
- Project source tag lists also include `HP_GES_STEAM_SUPPLY` and `HP_STEAM_NCG_CONTENT` where available; these are important for motive steam and NCG context.
- GES mode can be 80 percent, 40/60, or other train combinations in modelling notes. Mode changes can shift condenser pressure, motive steam use, and parasitic load.

Reinjection and BRIP:
- `Brine_Flow_To_Reinjection`: LP brine flow to reinjection context.
- `Total_Brine_Reinjection_Flow`: total brine reinjection flow context.
- `Brine_Flow_To_Reinjection_Pressure`: reinjection pressure context.
- `1st_Brip_A_Motor_Speed`, `1st_Brip_B_Motor_Speed`: first-stage BRIP motor speed context.
- `2nd_Stage_Brip_A_Current`, `2nd_Stage_Brip_B_Current`: second-stage BRIP current context.
- BRIP and reinjection staging can affect parasitic load and station operation.

## Common Investigation Logic

For a tag profile or incident:
- First decide whether the evidence looks like a data quality problem: outage, missing data, stale/stuck value, outlier, range breach, duplicated or flatline values, sudden impossible jump, or unexpected nulls.
- Then decide whether it might be a true process change: GES train change, BRIP/reinjection change, separator pressure change, turbine steam flow change, condenser/cooling water change, ambient condition change, outage/turnaround, or station operating mode change.
- Do not conclude root cause from one tag. Suggest related tags to check.
- If `Gross_Generator_Output` or `Net_Power` moves, check steam flow, separator pressure, condenser pressure, parasitic load, GES/vacuum pump current, cooling water, ambient temperature/humidity, and outage context.
- If condenser pressure moves, check cooling water temperature/flow, cooling tower fan current, ambient temperature/humidity, GES/vacuum pump current, NCG/GES context, and turbine exhaust/load.
- If parasitic load moves, check GES/vacuum pump current, BRIP/reinjection tags, cooling tower fan current, and station operating mode.
- If HP or LP steam flow moves, check separator pressures, turbine chamber pressures, GES motive steam, calculated Stodola flows, brine flow, and two-phase flow cross-checks.
- If well or two-phase flow tags move, check related well tags, HP steam flow, HP brine flow, LP brine/reinjection flow, and station enthalpy.
- If drift appears in a profile but data quality checks look clean, describe it as a possible operating-mode or process drift hypothesis, not a data fault.

## Model Drift Checklist

When explaining drift or persistent profile changes, check in this order when the supplied data supports it:

1. GES and BRIP system alignment with station actuals.
2. Parasitic load model alignment with actual parasitic load.
3. Condenser and cooling water model alignment.
4. GES motive steam calculated values compared with model constants.
5. Stodola coefficients compared with current calculated coefficients.

## Forecast And Optimiser Context

- Forecast models use recent station behaviour and weather inputs. One note says forecast inference uses half-hourly data and latest 24-hour medians for key station inputs such as HP venturi steam flow, HP brine flow, NCG content, HP steam pressure, LP steam flow, LP steam pressure, LP demister pressure, and cooling tower fan total current.
- Future weather forecast inputs include temperature and humidity. TID outage plans can affect future MW.
- Set point optimiser context uses measured two-phase flow and enthalpy from half-hourly averages and recommends LP set point, LP steam flow, and output MW.
- Optimiser exclusions include low gross output, large half-hourly gross output change, and unsupported GES modes. If an incident occurs during abnormal operation, avoid comparing it to normal-operation expectations without caveats.
