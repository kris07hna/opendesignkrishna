import { useState, useEffect, useRef } from 'react';
import { Icon } from './Icon';
import { useT } from '../i18n';

export interface UserFlowStep {
  kind: 'step' | 'thinking' | 'action' | 'shot' | 'whiteboard';
  text: string;
}

export interface UserFlowCardProps {
  url?: string;
  goal?: string;
  status?: 'crawling' | 'reasoning' | 'plotting' | 'complete' | 'error';
  steps?: UserFlowStep[];
  logs?: string[];
  sketchPath?: string | null;
  error?: string | null;
  runStreaming?: boolean;
  onRequestOpenFile?: (name: string) => void;
}

export function UserFlowCard({
  url,
  goal,
  status = 'crawling',
  steps = [],
  logs = [],
  sketchPath,
  error,
  runStreaming = false,
  onRequestOpenFile,
}: UserFlowCardProps) {
  const t = useT();
  const [expanded, setExpanded] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const isExecuting = runStreaming || status === 'crawling' || status === 'reasoning' || status === 'plotting';
  const isDone = status === 'complete' || Boolean(sketchPath);

  useEffect(() => {
    if (expanded && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, expanded]);

  const latestStep = steps[steps.length - 1];

  return (
    <div className="op-card op-user-flow-card" style={{
      margin: '8px 0',
      padding: '16px',
      borderRadius: '12px',
      background: 'var(--bg-panel, #0f172a)',
      border: '1px solid var(--border, #334155)',
      color: 'var(--fg, #f8fafc)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '12px', borderBottom: '1px solid var(--border, #334155)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(59,130,246,0.1)', color: 'var(--primary, #3b82f6)', border: '1px solid rgba(59,130,246,0.2)' }}>
            <Icon name="globe" size={18} />
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: 'var(--fg, #f8fafc)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              User Flow Generator
              {isExecuting && (
                <span style={{ fontSize: '11px', fontWeight: 500, padding: '2px 8px', borderRadius: '4px', background: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: '1px solid rgba(59,130,246,0.3)' }}>
                  Live Agent
                </span>
              )}
              {isDone && (
                <span style={{ fontSize: '11px', fontWeight: 500, padding: '2px 8px', borderRadius: '4px', background: 'rgba(16,185,129,0.15)', color: '#34d399', border: '1px solid rgba(16,185,129,0.3)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <Icon name="check" size={12} />
                  Whiteboard Ready
                </span>
              )}
            </h4>
            {url && (
              <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--fg-muted, #94a3b8)', maxWidth: '420px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {url} {goal ? `· ${goal}` : ''}
              </p>
            )}
          </div>
        </div>

        {sketchPath && onRequestOpenFile && (
          <button
            type="button"
            onClick={() => onRequestOpenFile('sitemap_flow.sketch.json')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 500,
              background: 'var(--primary, #3b82f6)',
              color: '#ffffff',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            <Icon name="pencil" size={12} />
            Open Whiteboard
          </button>
        )}
      </div>

      {/* Progress & Latest Step Status */}
      <div style={{ padding: '12px 0' }}>
        {latestStep ? (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '10px', borderRadius: '8px', background: 'var(--bg-input, #1e293b)', border: '1px solid var(--border, #334155)', fontSize: '12px' }}>
            <span style={{ fontFamily: 'monospace', textTransform: 'uppercase', fontWeight: 600, fontSize: '10px', letterSpacing: '0.05em', padding: '2px 6px', borderRadius: '4px', background: 'rgba(59,130,246,0.1)', color: 'var(--primary, #3b82f6)', border: '1px solid rgba(59,130,246,0.2)' }}>
              {latestStep.kind}
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: '11px', lineHeight: 1.5, flex: 1, color: 'var(--fg, #cbd5e1)' }}>
              {latestStep.text}
            </span>
          </div>
        ) : isExecuting ? (
          <div style={{ fontSize: '12px', color: 'var(--fg-muted, #94a3b8)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon name="spinner" size={14} />
            <span>Crawling target site with Playwright agent & extracting interactive elements...</span>
          </div>
        ) : error ? (
          <div style={{ fontSize: '12px', color: '#f87171', background: 'rgba(239,68,68,0.1)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.2)' }}>
            <strong>Error:</strong> {error}
          </div>
        ) : null}
      </div>

      {/* Logs Accordion */}
      {logs.length > 0 && (
        <div style={{ marginTop: '4px', borderTop: '1px solid var(--border, #334155)', paddingTop: '8px' }}>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              background: 'none',
              border: 'none',
              fontSize: '12px',
              color: 'var(--fg-muted, #94a3b8)',
              cursor: 'pointer',
              padding: '4px 0',
            }}
          >
            <span style={{ fontFamily: 'monospace', fontSize: '11px' }}>Execution Log ({logs.length} events)</span>
            <Icon name="chevron-down" size={14} style={{ transition: 'transform 0.2s', transform: expanded ? 'rotate(180deg)' : 'none' }} />
          </button>

          {expanded && (
            <div style={{ marginTop: '8px', maxHeight: '180px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '11px', background: 'var(--bg-input, #020617)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border, #1e293b)', color: 'var(--fg-muted, #cbd5e1)' }}>
              {logs.map((log, idx) => (
                <div key={idx} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.4, borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '2px' }}>
                  {log}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
