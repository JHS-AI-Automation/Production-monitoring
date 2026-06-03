import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/**
 * Vangt onverwachte render-fouten op zodat de gebruiker geen wit scherm krijgt,
 * maar een nette melding met een herlaad-knop. De fout gaat ook naar de
 * browser-console (zichtbaar voor support via F12).
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI-fout:", error, info.componentStack);
    // Stuur de fout naar de backend zodat hij in de server-logs terechtkomt (best-effort).
    void fetch("/api/client-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: error.message,
        stack: (info.componentStack ?? "").slice(0, 2000),
        url: window.location.href,
      }),
    }).catch(() => {
      /* foutrapportage mag zelf nooit een fout veroorzaken */
    });
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50 p-6 text-center">
        <div className="max-w-md">
          <h1 className="text-lg font-bold text-gray-800 mb-2">Er ging iets mis</h1>
          <p className="text-sm text-gray-500 mb-4">
            Het dashboard liep tegen een onverwachte fout aan. Probeer de pagina te
            herladen. Blijft het misgaan, geef dan deze melding door aan support.
          </p>
          <pre className="text-xs text-left bg-white border border-gray-200 rounded-lg p-3 overflow-auto text-red-600 mb-4">
            {this.state.error.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-dgs-600 text-white rounded-lg text-sm hover:bg-dgs-700 transition-colors"
          >
            Pagina herladen
          </button>
        </div>
      </div>
    );
  }
}
