import { useState, useRef, useEffect } from "react";
import { SendHorizontal, Database, ChevronDown, ChevronRight } from "lucide-react";
import { sendChatMessage, type ChatMessage } from "../api";

const SUGGESTIONS = [
  "Hoeveel alarmen waren er gisteren?",
  "Wat zijn de top 5 meest voorkomende alarmen deze week?",
  "Vergelijk het aantal alarmen van deze week met vorige week",
  "Welke uren van de dag hebben de meeste alarmen?",
  "Wat is de trend in Error-alarmen de afgelopen 30 dagen?",
];

function SqlBlock({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        <Database size={12} />
        <span>SQL</span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <pre className="mt-1 p-3 bg-gray-900 text-green-400 text-xs rounded-lg overflow-x-auto font-mono">
          {sql}
        </pre>
      )}
    </div>
  );
}

function DataTable({ data }: { data: Record<string, unknown>[] }) {
  const [open, setOpen] = useState(false);
  if (data.length === 0) return null;
  const cols = Object.keys(data[0]);
  const display = data.slice(0, 20);

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        <span>Data ({data.length} rijen)</span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div className="mt-1 overflow-x-auto rounded-lg border border-gray-200">
          <table className="text-xs w-full">
            <thead>
              <tr className="bg-gray-100">
                {cols.map((c) => (
                  <th key={c} className="px-3 py-1.5 text-left font-medium text-gray-600 whitespace-nowrap">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {display.map((row, i) => (
                <tr key={i} className={i % 2 ? "bg-gray-50" : ""}>
                  {cols.map((c) => (
                    <td key={c} className="px-3 py-1 text-gray-700 whitespace-nowrap">
                      {String(row[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > 20 && (
            <p className="px-3 py-1.5 text-xs text-gray-400 bg-gray-50 border-t">
              ... en {data.length - 20} meer rijen
            </p>
          )}
        </div>
      )}
    </div>
  );
}

const MAX_MESSAGES = 100;

function trimMessages(msgs: ChatMessage[]): ChatMessage[] {
  return msgs.length > MAX_MESSAGES ? msgs.slice(-MAX_MESSAGES) : msgs;
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;

    setInput("");
    setMessages((prev) => trimMessages([...prev, { role: "user", content: msg }]));
    setLoading(true);

    try {
      const res = await sendChatMessage(msg);
      setMessages((prev) =>
        trimMessages([
          ...prev,
          { role: "assistant", content: res.answer, sql: res.sql, data: res.data },
        ]),
      );
    } catch (e) {
      setMessages((prev) =>
        trimMessages([
          ...prev,
          { role: "assistant", content: `Fout: ${e instanceof Error ? e.message : "Onbekende fout"}` },
        ]),
      );
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex flex-col h-full -m-4 md:-m-8">
      <div className="px-8 py-4 border-b border-gray-200 bg-white">
        <h1 className="text-lg md:text-xl font-bold text-gray-800">Vraag het aan de data</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Stel vragen over alarmen, productie en palletstatus in gewoon Nederlands
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-14 h-14 rounded-2xl bg-dgs-100 flex items-center justify-center mb-4">
              <Database size={28} className="text-dgs-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-700 mb-2">
              Stel een vraag over de productiedata
            </h2>
            <p className="text-sm text-gray-400 mb-6 max-w-md">
              Ik vertaal je vraag naar SQL, voer de query uit op de database, en geef je het antwoord.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="px-3 py-1.5 text-sm text-gray-600 bg-white border border-gray-200 rounded-full hover:border-dgs-400 hover:text-dgs-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-dgs-600 text-white rounded-br-md"
                  : "bg-white border border-gray-200 text-gray-800 rounded-bl-md"
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              {msg.sql && <SqlBlock sql={msg.sql} />}
              {msg.data && msg.data.length > 0 && <DataTable data={msg.data} />}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1.5">
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:150ms]" />
                <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="px-8 py-4 border-t border-gray-200 bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex gap-3"
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Stel een vraag over de data..."
            disabled={loading}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-dgs-400 focus:border-transparent disabled:opacity-50 disabled:bg-gray-50"
            autoFocus
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-dgs-600 text-white rounded-xl hover:bg-dgs-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <SendHorizontal size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
