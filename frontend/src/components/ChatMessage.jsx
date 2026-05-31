import SourceCard from "./SourceCard";
import { Bot, User } from "lucide-react";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center mt-1
        ${isUser ? "bg-indigo-600" : "bg-gray-700"}`}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      <div className={`max-w-[80%] space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${isUser
            ? "bg-indigo-600 text-white rounded-tr-sm"
            : "bg-gray-800 text-gray-100 rounded-tl-sm"
          }`}>
          {message.content}
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className="w-full space-y-1.5">
            <p className="text-xs text-gray-500 px-1">
              {message.sources.length} source{message.sources.length > 1 ? "s" : ""} · {message.hops} search hop{message.hops > 1 ? "s" : ""}
            </p>
            {message.sources.map((s, i) => (
              <SourceCard key={i} source={s} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
