/**
 * SSE Stream Reader
 *
 * Reads Server-Sent Events from a Response stream and dispatches to callbacks.
 * Used by both text chat and voice chat.
 */

/** Callbacks for SSE events */
export interface SSEReadCallbacks {
  onToken: (text: string) => void;
  onFinal: (text: string) => void;
  onToolCall: (name: string, displayName?: string) => void;
  onAudio: (data: string) => void;
  onDone: (raw: string, tools: string[]) => void;
  onError: (text: string) => void;
}

/**
 * Reads an SSE stream and dispatches events to callbacks.
 */
export function readSSEStream(
  response: Response,
  targetNode: HTMLDivElement,
  callbacks: SSEReadCallbacks,
  lang: string = 'en'
): Promise<void> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  function pump(): Promise<void> {
    return reader.read().then((result) => {
      if (result.done) return;

      buffer += decoder.decode(result.value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop()!;

      for (const chunk of parts) {
        const line = chunk.split('\n').find((l) => l.startsWith('data:'));
        if (!line) continue;

        let payload: {
          type: string;
          text?: string;
          name?: string;
          display_name?: string;
          data?: string;
        };
        try {
          payload = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }

        if (targetNode.classList.contains('at-thinking')) {
          targetNode.classList.remove('at-thinking');
        }

        switch (payload.type) {
          case 'token':
            callbacks.onToken(payload.text || '');
            break;

          case 'final':
            callbacks.onFinal(payload.text || '');
            break;

          case 'tool_call': {
            const tools: string[] = JSON.parse(
              targetNode.dataset.tools || '[]'
            );
            const displayNames: Record<string, string> = JSON.parse(
              targetNode.dataset.displayNames || '{}'
            );

            if (payload.name && !tools.includes(payload.name)) {
              tools.push(payload.name);
              targetNode.dataset.tools = JSON.stringify(tools);
            }
            if (
              payload.display_name &&
              payload.name &&
              !displayNames[payload.name]
            ) {
              displayNames[payload.name] = payload.display_name;
              targetNode.dataset.displayNames = JSON.stringify(displayNames);
            }
            callbacks.onToolCall(payload.name || '', payload.display_name);
            break;
          }

          case 'audio':
            if (payload.data) {
              callbacks.onAudio(payload.data);
            }
            break;

          case 'done':
            if (targetNode.classList.contains('at-error')) return;
            if (!targetNode.dataset.raw?.trim()) {
              callbacks.onFinal(
                lang === 'ru'
                  ? 'Не удалось получить ответ.'
                  : 'No response.'
              );
            }
            let toolNames: string[] = [];
            try {
              toolNames = JSON.parse(targetNode.dataset.tools || '[]');
            } catch {
              /* ignore */
            }
            callbacks.onDone(targetNode.dataset.raw || '', toolNames);
            targetNode.dataset.saved = 'true';
            break;

          case 'error':
            targetNode.classList.remove('at-thinking');
            targetNode.classList.add('at-error');
            targetNode.textContent =
              payload.text ||
              (lang === 'ru'
                ? 'Произошла ошибка.'
                : 'An error occurred.');
            break;
        }
      }

      return pump();
    });
  }

  return pump();
}
