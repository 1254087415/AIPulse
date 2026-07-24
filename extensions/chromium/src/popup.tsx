import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { formatSubtitleEntries } from './platform/bilibili-subtitles';
import { extractDouyinVideoId } from './platform/douyin-share';
import {
  getDouyinDebuggerConsent,
  setDouyinDebuggerConsent,
} from './popup-debugger';
import type { FoundLink, SubmitMode, SubmitResult, SubtitleEntry } from './types';
import { cleanTrackingParams } from './utils';
import './popup.css';

const MODES: { value: SubmitMode; label: string }[] = [
  { value: 'archive', label: '归档' },
  { value: 'knowledge_check', label: '知识缺口分析' },
];

const SHORT_LINK_DOMAINS = ['b23.tv', 'xhslink.com', 'v.douyin.com'];

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

function parseTags(input: string): string[] {
  return input
    .split(/[,，]/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function normalizeUrl(url: string): string {
  const cleaned = cleanTrackingParams(url);
  return cleaned.endsWith('/') && cleaned.length > 1 ? cleaned.slice(0, -1) : cleaned;
}

const BV_PATTERN = /BV1[A-Za-z0-9]{8,}/;

function extractBvId(url: string): string | undefined {
  const match = url.match(BV_PATTERN);
  return match ? match[0] : undefined;
}

function isShortLink(url: string): boolean {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    return SHORT_LINK_DOMAINS.includes(host);
  } catch {
    return false;
  }
}

export function Popup() {
  const [tabUrl, setTabUrl] = useState('');
  const [tabId, setTabId] = useState<number | undefined>(undefined);
  const [foundLinks, setFoundLinks] = useState<FoundLink[]>([]);
  const [title, setTitle] = useState('');
  const [hasUserEditedTitle, setHasUserEditedTitle] = useState(false);
  const [tags, setTags] = useState('');
  const [mode, setMode] = useState<SubmitMode>('archive');
  const [status, setStatus] = useState('');
  const [isError, setIsError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [subtitleEntries, setSubtitleEntries] = useState<SubtitleEntry[]>([]);
  const [selectedSubtitleLan, setSelectedSubtitleLan] = useState('');
  const [subtitleLoading, setSubtitleLoading] = useState(false);
  const [shareUrlLoading, setShareUrlLoading] = useState(false);
  const [debuggerConsent, setDebuggerConsent] = useState<boolean | null>(null);
  const [debuggerConsentSubmitting, setDebuggerConsentSubmitting] = useState(false);
  const [version, setVersion] = useState('');
  const lastLinkUrlRef = useRef<string | null>(null);
  const pendingSubtitleLanRef = useRef<string | null>(null);

  const currentLink = useMemo<FoundLink | null>(() => {
    const normalizedTabUrl = normalizeUrl(tabUrl);
    const tabBvId = extractBvId(tabUrl);

    const exact = foundLinks.find((link) => {
      const normalizedLinkUrl = normalizeUrl(link.url);
      if (normalizedLinkUrl === normalizedTabUrl || link.url === tabUrl) {
        return true;
      }
      if (tabBvId && link.platform === 'bilibili') {
        const linkBvId = extractBvId(link.url);
        return linkBvId === tabBvId;
      }
      return false;
    });
    if (exact) return exact;

    // Homepage-style pages (e.g. Douyin feed) have no single canonical URL of
    // their own; surface the first recognized link instead of an empty state.
    return foundLinks[0] || null;
  }, [tabUrl, foundLinks]);

  const subtitleOptions = currentLink?.metadata?.subtitleOptions || [];
  // Douyin's official share short link (https://v.douyin.com/xxx) is what the
  // download pipeline consumes; prefer it for display, copy and submit when
  // the extractor resolved one. The canonical long URL stays in link.url.
  const displayUrl = currentLink?.metadata?.shareUrl || currentLink?.url || '';

  const loadState = async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const url = tab?.url || '';
      setTabUrl(url);
      setTabId(tab?.id);

      const response = (await chrome.runtime.sendMessage({
        type: 'GET_FOUND_LINKS',
        tabId: tab?.id,
      })) as { links?: FoundLink[] } | undefined;
      let links = response?.links || [];

      // No stored entry for this tab (e.g. the page was open before the
      // extension loaded, or its entry was cleared): ask the content script
      // to rescan now so the popup always reflects the current tab.
      if (links.length === 0 && tab?.id) {
        try {
          const rescan = (await chrome.tabs.sendMessage(tab.id, {
            type: 'RESCAN',
          })) as { ok: boolean; links?: FoundLink[] } | undefined;
          if (rescan?.ok && rescan.links) {
            links = rescan.links;
          }
        } catch {
          // No content script on this page (unsupported site) — show empty state.
        }
      }

      setFoundLinks(links);

      const consent = await getDouyinDebuggerConsent();
      setDebuggerConsent(consent === true);
    } catch (err) {
      setStatus(`获取页面失败: ${getErrorMessage(err)}`);
      setIsError(true);
    }
  };

  useEffect(() => {
    loadState();
    setVersion(chrome.runtime.getManifest().version);
  }, []);

  const handleSubtitleChange = useCallback(async (lan: string) => {
    setSelectedSubtitleLan(lan);
    const option = subtitleOptions.find((opt) => opt.lan === lan);
    if (!option || !tabId) return;
    setSubtitleLoading(true);
    pendingSubtitleLanRef.current = lan;
    try {
      const response = (await chrome.tabs.sendMessage(tabId, {
        type: 'FETCH_SUBTITLE',
        subtitleUrl: option.subtitleUrl,
      })) as { ok: boolean; entries?: SubtitleEntry[]; error?: string };
      if (pendingSubtitleLanRef.current !== lan) return;
      if (response.ok && response.entries) {
        setSubtitleEntries(response.entries);
        setStatus('字幕已加载');
        setIsError(false);
      } else {
        setStatus(`字幕加载失败: ${response.error || '未知错误'}`);
        setIsError(true);
      }
    } catch (err) {
      if (pendingSubtitleLanRef.current !== lan) return;
      setStatus(`字幕加载失败: ${getErrorMessage(err)}`);
      setIsError(true);
    } finally {
      setSubtitleLoading(false);
    }
  }, [subtitleOptions, tabId]);

  useEffect(() => {
    if (!currentLink) {
      setStatus('当前页面未识别到支持的链接');
      setIsError(true);
      return;
    }
    setStatus('已识别到支持的链接');
    setIsError(false);
    if (currentLink.url !== lastLinkUrlRef.current && !hasUserEditedTitle) {
      lastLinkUrlRef.current = currentLink.url;
      setTitle(currentLink.title || '');
    }
    const initialLan =
      currentLink.metadata?.selectedSubtitleLan ||
      currentLink.metadata?.subtitleOptions?.[0]?.lan ||
      '';
    setSelectedSubtitleLan(initialLan);
    setSubtitleEntries(currentLink.metadata?.subtitleEntries || []);

    // Auto-load the default subtitle track when the popup opens.
    if (
      tabId &&
      initialLan &&
      subtitleOptions.length > 0 &&
      !currentLink.metadata?.subtitleEntries?.length
    ) {
      handleSubtitleChange(initialLan);
    }
  }, [currentLink, hasUserEditedTitle, tabId, subtitleOptions, handleSubtitleChange]);

  // For Douyin links, try to capture the official share short link by hovering
  // the share button in the active slide. This is necessary because Douyin's
  // web_shorten endpoint is protected by anti-bot signatures that we cannot
  // generate ourselves.
  //
  // Important: this effect must NOT trigger the debugger path unless the user
  // has explicitly accepted the consent prompt. chrome.debugger.attach displays
  // a Chrome-level "Debugger is attached" banner that we never want to show
  // without warning.
  useEffect(() => {
    if (
      !currentLink ||
      currentLink.platform !== 'douyin' ||
      currentLink.metadata?.shareUrl ||
      !tabId ||
      debuggerConsent !== true
    ) {
      return;
    }
    const videoId = extractDouyinVideoId(currentLink.url);
    if (!videoId) return;

    let cancelled = false;
    setShareUrlLoading(true);
    setStatus('正在获取抖音分享短链...');
    setIsError(false);
    chrome.tabs
      .sendMessage(tabId, { type: 'FETCH_DOUYIN_SHARE_URL', videoId })
      .then((response) => {
        if (cancelled) return;
        const res = response as { ok: boolean; shareUrl?: string } | undefined;
        if (res?.ok && res.shareUrl) {
          setFoundLinks((prev) =>
            prev.map((link) =>
              link.url === currentLink.url
                ? {
                      ...link,
                      metadata: {
                        platform: link.platform,
                        url: link.url,
                        title: link.metadata?.title || link.title || '',
                        subtitleOptions: link.metadata?.subtitleOptions || [],
                        subtitleEntries: link.metadata?.subtitleEntries || [],
                        selectedSubtitleLan: link.metadata?.selectedSubtitleLan || '',
                        ...link.metadata,
                        shareUrl: res.shareUrl,
                      },
                    }
                : link
            )
          );
          setStatus('抖音短链已获取');
          setIsError(false);
        } else {
          setStatus('未获取到抖音短链，可悬停分享按钮后重试');
          setIsError(true);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setStatus(`获取抖音短链失败: ${getErrorMessage(err)}`);
          setIsError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setShareUrlLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [currentLink, tabId, debuggerConsent]);

  const handleDebuggerConsent = useCallback(
    async (accepted: boolean) => {
      if (debuggerConsentSubmitting) return;
      setDebuggerConsentSubmitting(true);
      try {
        await setDouyinDebuggerConsent(accepted);
        setDebuggerConsent(accepted);
        setStatus(accepted ? '已启用抖音短链自动捕获' : '已禁用抖音短链自动捕获');
        setIsError(false);
      } catch (err) {
        setStatus(`保存偏好失败: ${getErrorMessage(err)}`);
        setIsError(true);
      } finally {
        setDebuggerConsentSubmitting(false);
      }
    },
    [debuggerConsentSubmitting]
  );

  const handleTitleChange = (value: string) => {
    setTitle(value);
    setHasUserEditedTitle(true);
  };

  const handleCopyUrl = async () => {
    if (!currentLink) return;
    try {
      await navigator.clipboard.writeText(displayUrl);
      setStatus('链接已复制');
      setIsError(false);
    } catch (err) {
      setStatus(`复制失败: ${getErrorMessage(err)}`);
      setIsError(true);
    }
  };

  const handleCopySubtitle = async () => {
    if (subtitleEntries.length === 0) return;
    try {
      await navigator.clipboard.writeText(formatSubtitleEntries(subtitleEntries));
      setStatus('字幕已复制');
      setIsError(false);
    } catch (err) {
      setStatus(`复制失败: ${getErrorMessage(err)}`);
      setIsError(true);
    }
  };

  const handleSubmit = async () => {
    if (!currentLink) return;
    setLoading(true);
    setStatus('提交中...');
    setIsError(false);
    try {
      const trimmedTitle = title.trim();
      const result = (await chrome.runtime.sendMessage({
        type: 'SUBMIT_URL',
        url: displayUrl,
        title: trimmedTitle || undefined,
        mode,
        tags: parseTags(tags),
        subtitle_text: subtitleEntries.length > 0 ? formatSubtitleEntries(subtitleEntries) : undefined,
        subtitle_language: selectedSubtitleLan || undefined,
      })) as { ok: boolean; result?: SubmitResult; error?: string };
      if (result.ok) {
        setStatus(`已提交: ${result.result?.task_id}`);
      } else {
        setStatus(`失败: ${result.error || '请启动 AIPulse 桌面应用'}`);
        setIsError(true);
      }
    } catch (err) {
      setStatus(`失败: ${getErrorMessage(err)}`);
      setIsError(true);
    } finally {
      setLoading(false);
    }
  };

  const platformLabel = currentLink?.platform ? currentLink.platform.toUpperCase() : '未知';
  const subtitlePreview = formatSubtitleEntries(subtitleEntries);

  return (
    <div className="popup">
      <header className="popup-header">
        <div className="popup-title">
          <strong>AIPulse Clipper</strong>
          {version && <span className="version-badge">v{version}</span>}
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={loadState}
          disabled={loading || subtitleLoading || shareUrlLoading}
          title="刷新"
          aria-label="刷新"
        >
          ↻
        </button>
      </header>

      <p className={`status ${isError ? 'is-error' : ''}`} role="status" aria-live="polite">
        {status}
      </p>

      {currentLink?.platform === 'douyin' && debuggerConsent === false && (
        <section className="debugger-card" aria-labelledby="debugger-consent-title">
          <h2 id="debugger-consent-title">启用抖音分享短链自动捕获</h2>
          <p>
            抖音分享短链（v.douyin.com）需要浏览器附加 Chrome 调试器，附加期间会在浏览器顶部显示黄色的 "Debugger is attached" 提示条。点击"启用"以开启自动悬停抓取；点击"暂不启用"将仅使用普通长链接。
          </p>
          <div className="debugger-actions">
            <button
              type="button"
              className="debugger-confirm"
              onClick={() => handleDebuggerConsent(true)}
              disabled={debuggerConsentSubmitting}
              aria-label="启用抖音短链自动捕获"
            >
              启用
            </button>
            <button
              type="button"
              className="debugger-decline"
              onClick={() => handleDebuggerConsent(false)}
              disabled={debuggerConsentSubmitting}
              aria-label="暂不启用抖音短链自动捕获"
            >
              暂不启用
            </button>
          </div>
        </section>
      )}

      {currentLink ? (
        <>
          <section className="link-card">
            <div className="platform-badge">{platformLabel}</div>
            <label className="field">
              <span className="field-label">标题</span>
              <input
                type="text"
                value={title}
                onChange={(e) => handleTitleChange(e.target.value)}
                placeholder="输入标题"
                disabled={loading}
              />
            </label>
            <label className="field">
              <span className="field-label">链接</span>
              <span className="url-value" title={displayUrl}>
                {isShortLink(displayUrl) && <span className="short-badge">短链</span>}
                {displayUrl}
              </span>
            </label>
            <label className="field">
              <span className="field-label">标签</span>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="用逗号分隔"
                disabled={loading}
              />
            </label>

            {subtitleOptions.length > 0 && (
              <>
                <label className="field">
                  <span className="field-label">字幕</span>
                  <select
                    value={selectedSubtitleLan}
                    onChange={(e) => handleSubtitleChange(e.target.value)}
                    disabled={loading || subtitleLoading || shareUrlLoading}
                  >
                    {subtitleOptions.map((option) => (
                      <option key={option.lan} value={option.lan}>
                        {option.lanDoc}
                      </option>
                    ))}
                  </select>
                </label>
                {subtitleEntries.length > 0 && (
                  <label className="field">
                    <span className="field-label">预览</span>
                    <textarea
                      className="subtitle-preview"
                      value={subtitlePreview}
                      readOnly
                      rows={6}
                    />
                  </label>
                )}
              </>
            )}
          </section>

          <div className="mode-selector" role="group" aria-label="提交模式">
            {MODES.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                className={mode === value ? 'active' : ''}
                onClick={() => setMode(value)}
                disabled={loading || subtitleLoading || shareUrlLoading}
                aria-pressed={mode === value}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="actions">
            <button type="button" onClick={handleCopyUrl} disabled={loading || subtitleLoading || shareUrlLoading}>
              复制链接
            </button>
            {subtitleEntries.length > 0 && (
              <button
                type="button"
                onClick={handleCopySubtitle}
                disabled={loading || subtitleLoading || shareUrlLoading}
              >
                复制字幕
              </button>
            )}
          </div>
          <button
            type="button"
            className="primary submit-btn"
            onClick={handleSubmit}
            disabled={loading || subtitleLoading || shareUrlLoading}
          >
            归档到 AIPulse
          </button>
        </>
      ) : (
        <div className="empty-state">
          <p>打开 B 站、抖音、小红书或微信公众号页面后，这里会自动识别主链接。</p>
        </div>
      )}
    </div>
  );
}

// Guard: skip the production mount when running inside Vitest.
// The test file dynamically imports Popup and renders it via @testing-library,
// so the top-level createRoot must not fire a second time.
// In a real browser or production build this always runs.
if (!import.meta.env?.VITEST) {
  ReactDOM.createRoot(document.getElementById('root')!).render(<Popup />);
}
