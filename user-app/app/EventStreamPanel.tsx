import { RTVIEvent } from "@pipecat-ai/client-js";
import {
  usePipecatEventStream,
  type PipecatEventGroup,
  type PipecatEventLog,
} from "@pipecat-ai/voice-ui-kit";
import { Activity, ChevronDown, ChevronRight, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AgentEvent } from "./ClientApp";

const formatTimestamp = (date: Date) => {
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  });
};

const getEventColor = (type: string) => {
  if (type.includes("error") || type.includes("Error"))
    return "event-tone-error";
  if (type.includes("warning") || type.includes("Warning"))
    return "event-tone-warning";
  if (type.includes("bot")) return "event-tone-bot";
  if (type.includes("metrics")) return "event-tone-muted";
  if (type.includes("user")) return "event-tone-user";
  if (type.includes("transport")) return "event-tone-warning";
  return "event-tone-default";
};

type EventStreamRowProps = {
  event: PipecatEventLog;
  eventColorClass: string;
  isFirstInGroup: boolean;
  hasMultiple: boolean;
  onToggle?: () => void;
  formatTimestamp: (date: Date) => string;
};

function EventStreamRow({
  event,
  eventColorClass,
  isFirstInGroup,
  hasMultiple,
  onToggle,
  formatTimestamp,
}: EventStreamRowProps) {
  return (
    <div className="event-row">
      {hasMultiple && isFirstInGroup ? (
        <button type="button" className="event-chevron" onClick={onToggle} title="折叠事件组">
          <ChevronDown />
        </button>
      ) : (
        <span className="event-branch" />
      )}
      <div className="event-row-content">
        <time>{formatTimestamp(event.timestamp)}</time>
        <strong className={eventColorClass}>{event.type}</strong>
        <span className="event-data">
          {event.data ? JSON.stringify(event.data).slice(0, 100) : "null"}
          {event.data && JSON.stringify(event.data).length > 100 ? "..." : ""}
        </span>
      </div>
    </div>
  );
}

export function EventStreamPanel({
  agentEvents,
  onClose,
}: {
  agentEvents: AgentEvent[];
  onClose?: () => void;
}) {
  const { events, groups } = usePipecatEventStream({
    maxEvents: 500,
    ignoreEvents: [
      RTVIEvent.LocalAudioLevel,
      RTVIEvent.RemoteAudioLevel,
      RTVIEvent.BotTtsText,
      RTVIEvent.BotLlmText,
    ],
    groupConsecutive: true,
  });
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "auto", block: "nearest" });
  }, [agentEvents, events]);

  const eventGroups: ReadonlyArray<PipecatEventGroup> = groups;

  const toggleGroup = (groupId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  return (
    <aside className="event-monitor" aria-label="系统事件监控">
      <header className="event-monitor-header">
        <div className="event-monitor-title">
          <Activity />
          <div>
            <strong>系统事件</strong>
            <span>实时调用详情</span>
          </div>
        </div>
        <div className="event-monitor-actions">
          <span className="event-count"><i />{events.length + agentEvents.length}</span>
          {onClose && (
            <button type="button" onClick={onClose} title="收起系统事件">
              <X />
            </button>
          )}
        </div>
      </header>
      <div className="event-monitor-content">
          {events.length === 0 && agentEvents.length === 0 ? (
            <div className="event-empty">
              <Activity />
              <span>等待通话事件</span>
            </div>
          ) : (
            <div className="event-list">
              {agentEvents.map((event) => (
                <div
                  key={event.id}
                  className="event-row event-agent-row"
                  data-event-type={event.type}
                  data-run-id={
                    typeof event.data.run_id === "string" ? event.data.run_id : undefined
                  }
                >
                  <span className="event-branch" />
                  <div className="event-row-content">
                    <time>{formatTimestamp(event.timestamp)}</time>
                    <strong className={getEventColor(event.type)}>{event.type}</strong>
                    <span className="event-data">{JSON.stringify(event.data).slice(0, 140)}</span>
                  </div>
                </div>
              ))}
              {eventGroups.map((group) => {
                const isExpanded = expandedGroups.has(group.id);
                const hasMultiple = group.events.length > 1;
                const eventColor = getEventColor(group.type);

                if (!hasMultiple || isExpanded) {
                  return group.events.map((event, index) => (
                    <EventStreamRow
                      key={event.id}
                      event={event}
                      eventColorClass={eventColor}
                      isFirstInGroup={hasMultiple && index === 0}
                      hasMultiple={hasMultiple}
                      onToggle={() => toggleGroup(group.id)}
                      formatTimestamp={formatTimestamp}
                    />
                  ));
                } else {
                  return (
                    <div key={group.id} className="event-row event-group-row">
                      <button
                        type="button"
                        onClick={() => toggleGroup(group.id)}
                        className="event-chevron"
                        title="展开事件组"
                      >
                        <ChevronRight />
                      </button>
                      <div className="event-row-content">
                        <time>{formatTimestamp(group.events[0].timestamp)}</time>
                        <strong className={eventColor}>
                          {group.type}
                        </strong>
                        <span className="event-group-count">
                          {group.events.length} 条
                        </span>
                      </div>
                    </div>
                  );
                }
              })}
              <div ref={eventsEndRef} />
            </div>
          )}
      </div>
    </aside>
  );
}
