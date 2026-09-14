/** Illustrative functional outputs on existing hosts, not extra physical devices.
 * Values and periods are editable design defaults, not measured requirements.
 */
export const automotiveFunctionOutputs = [
  ["BodyControl", "Innenraumueberwachung", "InnenraumBelegung", "Personen", 0, 9, 1],
  ["BodyControl", "Einbruchueberwachung", "InnenraumBewegungsintensitaet", "%", 0, 100, 1],
  ["Klimatisierung", "InnenraumTemperaturregelung", "InnenraumTemperaturIst", "degC", -40, 85, 0.1],
  ["Klimatisierung", "InnenraumTemperaturregelung", "InnenraumTemperaturSoll", "degC", 16, 30, 0.1],
  ["Klimatisierung", "Luftqualitaetsregelung", "InnenraumCO2", "ppm", 0, 10000, 1],
  ["Klimatisierung", "Entfeuchtung", "InnenraumLuftfeuchte", "%", 0, 100, 0.1],
  ["Klimatisierung", "Luftverteilung", "GeblaeseLeistung", "%", 0, 100, 1],
  ["Infotainment", "RadioFM", "RadioFrequenz", "MHz", 87.5, 108, 0.1],
  ["Infotainment", "RadioDAB", "DABEmpfangsqualitaet", "%", 0, 100, 1],
  ["Infotainment", "Medienwiedergabe", "MedienFortschritt", "s", 0, 86400, 1],
  ["Infotainment", "Bedienelemente", "BedienLautstaerke", "%", 0, 100, 1],
  ["Infotainment", "Navigation", "NavigationReststrecke", "m", 0, 2000000, 1],
  ["Infotainment", "Navigation", "NavigationRestzeit", "s", 0, 172800, 1],
  ["Telematik", "GNSSPositionierungGPS", "GNSSBreitengrad", "deg", -90, 90, 0.000001],
  ["Telematik", "GNSSPositionierungGPS", "GNSSLaengengrad", "deg", -180, 180, 0.000001],
  ["Telematik", "GNSSPositionierungGPS", "GNSSPositionsgenauigkeit", "m", 0, 1000, 0.1],
  ["Konnektivitaet", "InternetMobilfunk", "InternetDatenrate", "Mbit/s", 0, 10000, 0.1],
  ["Konnektivitaet", "WLAN", "WLANSignalstaerke", "dBm", -120, 0, 1],
  ["Konnektivitaet", "Bluetooth", "BluetoothVerbindungen", "Verbindungen", 0, 16, 1],
  ["Soundsystem", "Audioausgabe", "AudioLautstaerke", "%", 0, 100, 1],
] as const;
