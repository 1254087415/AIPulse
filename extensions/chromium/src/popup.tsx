import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import type { FoundLink, SubmitMode, SubmitResult } from './types';
import './popup.css';

function Popup() {
  const [tabUrl, setTabUrl] = useState<string>('');
  const [links, setLinks] = useState<FoundLink[]>([]);
  const [selectedUrl, setSelectedUrl] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const url = tabs[0]?.url || '';
      setTabUrl(url);
      setSelectedUrl(url);
    });

    chrome.runtime.sendMessage({ type: 'GET_FOUND_LINKS' }, (response) => {
      if (response?.links) {
        setLinks(response.links);
      }
    });
  }, []);

  const handleSubmit = async (mode: SubmitMode) => {
    if (!selectedUrl) return;
    setLoading(true);
    setStatus('提交中...');
    try {
      const result = (await chrome.runtime.sendMessage({
        type: 'SUBMIT_URL',
        url: selectedUrl,
        mode,
      })) as { ok: boolean; result?: SubmitResult; error?: string };
      if (result.ok) {
        setStatus(`已提交: ${result.result?.task_id}`);
      } else {
        setStatus(`失败: ${result.error || '请启动 AIPulse 桌面应用'}`);
      }
    } catch (err) {
      setStatus(`失败: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="popup-container">
      <h1>AIPulse Clipper</h1>
      <select
        value={selectedUrl}
        onChange={(e) => setSelectedUrl(e.target.value)}
        disabled={loading}
      >
        <option value={tabUrl}>当前页面</option>
        {links.map((link) => (
          <option key={link.url} value={link.url}>
            {link.platform}: {link.url}
          </option>
        ))}
      </select>
      <div className="actions">
        <button onClick={() => handleSubmit('archive')} disabled={loading || !selectedUrl}>
          归档到 AIPulse
        </button>
        <button
          onClick={() => handleSubmit('knowledge_check')}
          disabled={loading || !selectedUrl}
        >
          归档并分析知识缺口
        </button>
      </div>
      {status && <p className="status">{status}</p>}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(<Popup />);
