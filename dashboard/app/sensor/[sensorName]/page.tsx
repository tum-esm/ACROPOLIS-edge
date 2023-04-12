import { SENSOR_IDS } from "@/components/constants";

// TODO: render overview section (last measurement, last log, sensor id)
// TODO: render tbs for logs and measurements
// TODO: render logs
// TODO: render measurements

export function generateStaticParams() {
  return Object.values(SENSOR_IDS).map((sensorName) => ({
    sensorName,
  }));
}

export default function Page({ params }: { params: { sensorName: string } }) {
  const sensorId = SENSOR_IDS[params.sensorName];

  return (
    <h1>
      Sensor {params.sensorName} (ID: {sensorId})
    </h1>
  );
}
