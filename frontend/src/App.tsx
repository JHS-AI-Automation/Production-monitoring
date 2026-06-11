import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import AlarmList from "./pages/AlarmList";
import Production from "./pages/Production";
import Pallets from "./pages/Pallets";
import Trends from "./pages/Trends";
import Chat from "./pages/Chat";
import MotorOverview from "./pages/maintenance/MotorOverview";
import { FEATURES } from "./features";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/alarms" element={<AlarmList />} />
        <Route path="/production" element={<Production />} />
        <Route path="/pallets" element={<Pallets />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/chat" element={<Chat />} />
        {FEATURES.maintenance && <Route path="/maintenance" element={<MotorOverview />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
