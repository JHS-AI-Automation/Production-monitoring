import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { REASON_GROUPS, statesByReason } from "../lib/machineStates";

// Uitklapbare legenda van de PackML-machinetoestanden (codes 1-17) bij de OEE-sectie.
// Gegroepeerd naar de REDEN waarom er geen productie is (storing, geblokkeerd,
// pauze, ...), zodat de klant ziet waaróm de lijn stilstaat. Standaard dichtgeklapt
// zodat de OEE-cijfers niet worden weggedrukt.
export default function MachineStateLegend() {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-5 border-t border-gray-100 pt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Machinetoestanden (PackML)
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-gray-400">
            De machine rapporteert per eenheid een toestand (codes 1-17, gelijk aan de
            Grafana-tijdlijn), hier gegroepeerd naar de reden waarom er geen productie is.
            Voor de OEE telt alleen <span className="font-medium text-gray-600">Execute</span> als
            productieve draaitijd.
          </p>

          {REASON_GROUPS.map((group) => (
            <div key={group.reason}>
              <h4 className="text-xs font-semibold text-gray-600">
                {group.title}{" "}
                <span className="font-normal text-gray-400">— {group.note}</span>
              </h4>
              <div className="mt-1.5 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
                {statesByReason(group.reason).map((s) => (
                  <div key={s.code} className="flex items-center gap-2 text-xs">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: s.color }}
                    />
                    <span className="tabular-nums text-gray-400 w-5 text-right">{s.code}</span>
                    <span className="font-medium text-gray-700">{s.name}</span>
                    <span className="text-gray-400 truncate">{s.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
