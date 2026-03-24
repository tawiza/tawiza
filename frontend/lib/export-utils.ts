/**
 * Export utilities for conversations and reports
 */

import { ConversationDetail } from './api-conversations';

// Types
export interface ExportOptions {
  format: 'pdf' | 'json' | 'csv' | 'md';
  includeMetadata?: boolean;
  title?: string;
}

/**
 * Export conversation as JSON
 */
export function exportAsJson(conversation: ConversationDetail): void {
  const data = {
    ...conversation,
    exportedAt: new Date().toISOString(),
  };

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  });
  downloadBlob(blob, `tajine-conversation-${conversation.id}.json`);
}

/**
 * Export conversation as Markdown
 */
export function exportAsMarkdown(conversation: ConversationDetail): void {
  const lines: string[] = [
    `# ${conversation.title}`,
    '',
    `**Niveau cognitif:** ${formatLevel(conversation.level)}`,
    `**Date:** ${formatDate(conversation.created_at)}`,
    '',
    '---',
    '',
  ];

  for (const msg of conversation.messages) {
    const role = msg.role === 'user' ? '**Vous**' : '**TAJINE**';
    lines.push(`### ${role}`);
    lines.push('');
    lines.push(msg.content);
    lines.push('');
    lines.push(`_${formatDate(msg.created_at)}_`);
    lines.push('');
    lines.push('---');
    lines.push('');
  }

  lines.push('');
  lines.push(`_Exporte depuis Tawiza TAJINE le ${formatDate(new Date().toISOString())}_`);

  const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
  downloadBlob(blob, `tajine-conversation-${conversation.id}.md`);
}

/**
 * Export conversation as CSV
 */
export function exportAsCsv(conversation: ConversationDetail): void {
  const headers = ['Timestamp', 'Role', 'Content'];
  const rows = conversation.messages.map((msg) => [
    msg.created_at,
    msg.role,
    `"${msg.content.replace(/"/g, '""')}"`, // Escape quotes
  ]);

  const csv = [
    headers.join(','),
    ...rows.map((row) => row.join(',')),
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  downloadBlob(blob, `tajine-conversation-${conversation.id}.csv`);
}

/**
 * Export conversation as PDF using backend WeasyPrint generation.
 *
 * Uses the server-side /api/v1/export/pdf endpoint for professional
 * PDF output with proper styling, page numbers, and formatting.
 * Falls back to browser print if backend is unavailable.
 */
export async function exportAsPdf(
  conversation: ConversationDetail,
  options?: { useBrowserFallback?: boolean }
): Promise<void> {
  // Build content from messages
  const content = conversation.messages
    .map((msg) => {
      const role = msg.role === 'user' ? '**Vous:**' : '**TAJINE:**';
      return `${role}\n\n${msg.content}`;
    })
    .join('\n\n---\n\n');

  // Try backend PDF generation first
  if (!options?.useBrowserFallback) {
    try {
      const response = await fetch('/api/v1/export/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversation.id,
          content,
          title: conversation.title || 'Rapport TAJINE',
          metadata: {
            territory: conversation.territory || 'France',
            sources: conversation.sources || ['TAJINE'],
            confidence: conversation.confidence || 70,
            mode: conversation.mode || 'RAPIDE',
          },
          format: 'report',
        }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const disposition = response.headers.get('Content-Disposition');
        const filename = disposition?.match(/filename="(.+)"/)?.[1] ||
          `tajine-rapport-${conversation.id}.pdf`;
        downloadBlob(blob, filename);
        return;
      }

      console.warn('Backend PDF generation failed, using browser fallback');
    } catch (err) {
      console.warn('Backend PDF unavailable:', err);
    }
  }

  // Fallback to browser-based print
  exportAsPdfBrowser(conversation);
}

/**
 * Browser-based PDF export using print dialog.
 * Used as fallback when backend is unavailable.
 */
function exportAsPdfBrowser(conversation: ConversationDetail): void {
  const html = generatePdfHtml(conversation);
  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);

  const printWindow = window.open(url, '_blank');
  if (!printWindow) {
    alert('Veuillez autoriser les popups pour exporter en PDF');
    URL.revokeObjectURL(url);
    return;
  }

  // Clean up URL after print window is ready
  printWindow.onload = () => {
    printWindow.print();
    // Revoke URL after a delay to ensure print dialog has loaded
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
}

/**
 * Generate HTML content for PDF export
 */
function generatePdfHtml(conversation: ConversationDetail): string {
  const messagesHtml = conversation.messages.map((msg) => `
    <div class="message ${msg.role}">
      <div class="role">${msg.role === 'user' ? 'Vous' : 'TAJINE'}</div>
      <div class="content">${formatContentForHtml(msg.content)}</div>
      <div class="timestamp">${formatDate(msg.created_at)}</div>
    </div>
  `).join('');

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${escapeHtml(conversation.title)} - TAJINE</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 800px;
      margin: 0 auto;
      padding: 40px 20px;
      line-height: 1.6;
      color: #1a1a1a;
    }
    h1 {
      color: #2e3440;
      border-bottom: 2px solid #88c0d0;
      padding-bottom: 10px;
    }
    .metadata {
      color: #666;
      font-size: 0.9em;
      margin-bottom: 30px;
    }
    .message {
      margin: 20px 0;
      padding: 15px;
      border-radius: 8px;
    }
    .user {
      background: #eceff4;
      margin-left: 40px;
    }
    .assistant {
      background: #e5f3f8;
      border-left: 3px solid #88c0d0;
    }
    .role {
      font-weight: bold;
      margin-bottom: 8px;
    }
    .timestamp {
      font-size: 0.8em;
      color: #888;
      margin-top: 10px;
    }
    .footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #ddd;
      font-size: 0.8em;
      color: #888;
      text-align: center;
    }
    @media print {
      body { padding: 0; }
      .message { page-break-inside: avoid; }
    }
  </style>
</head>
<body>
  <h1>${escapeHtml(conversation.title)}</h1>
  <div class="metadata">
    <p><strong>Niveau cognitif:</strong> ${formatLevel(conversation.level)}</p>
    <p><strong>Date:</strong> ${formatDate(conversation.created_at)}</p>
  </div>
  ${messagesHtml}
  <div class="footer">
    Exporte depuis Tawiza TAJINE le ${formatDate(new Date().toISOString())}
  </div>
</body>
</html>`;
}

/**
 * Generate a shareable link for a conversation
 */
export function generateShareableLink(conversationId: string): string {
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
  return `${baseUrl}/dashboard/ai-chat?share=${conversationId}`;
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const result = document.execCommand('copy');
    document.body.removeChild(textarea);
    return result;
  }
}

// Helper functions
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function formatLevel(level: string): string {
  const levels: Record<string, string> = {
    reactive: 'Reactif',
    analytical: 'Analytique',
    strategic: 'Strategique',
    prospective: 'Prospectif',
    theoretical: 'Theorique',
  };
  return levels[level] || level;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatContentForHtml(content: string): string {
  // Basic markdown-like formatting
  return escapeHtml(content)
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>');
}
