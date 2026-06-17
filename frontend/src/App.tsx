import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import AlarmList from "./pages/AlarmList";
import Production from "./pages/Production";
import Trends from "./pages/Trends";
import Chat from "./pages/Chat";
import LoadingSpinner from "./components/LoadingSpinner";
import { FEATURES } from "./features";

// Lazy (trunk-based vlag-discipline): maintenance-code wordt als aparte chunk
// gebouwd en alleen geladen als de route echt wordt bezocht. Met de vlag uit
// zit de feature dus niet in de initiele bundle die gebruikers downloaden.
const MotorOverview = lazy(() => import("./pages/maintenance/MotorOverview"));

// Pallets: feature-flag uit (palletstatus hoort niet bij deze lijn). Lazy, dus
// niet in de initiele bundle zolang de vlag uit staat. Aanzetten in features.ts.
const Pallets = lazy(() => import("./pages/Pallets"));

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/alarms" element={<AlarmList />} />
        <Route path="/production" element={<Production />} />
        {FEATURES.pallets && (
          <Route
            path="/pallets"
            element={
              <Suspense fallback={<LoadingSpinner />}>
                <Pallets />
              </Suspense>
            }
          />
        )}
        <Route path="/trends" element={<Trends />} />
        <Route path="/chat" element={<Chat />} />
        {FEATURES.maintenance && (
          <Route
            path="/maintenance"
            element={
              <Suspense fallback={<LoadingSpinner />}>
                <MotorOverview />
              </Suspense>
            }
          />
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
