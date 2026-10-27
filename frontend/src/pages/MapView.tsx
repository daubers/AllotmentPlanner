import MapEditor from "../map/MapEditor";
import { useAllotment } from "./AllotmentLayout";

export default function MapView() {
  const { id, canEdit } = useAllotment();
  return <MapEditor allotmentId={id} canEdit={canEdit} />;
}
