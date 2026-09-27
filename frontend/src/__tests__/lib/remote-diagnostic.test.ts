import { reportDiagnostic } from '@/lib/remote-log';

describe('durable client diagnostics', () => {
  it('posts only safe metadata with credentials and no raw error or token', async () => {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true });
    global.fetch = fetchMock;
    reportDiagnostic('audio_play_failed', { jobId: 31, gameId: 5, operationId: 'voice:31', phase: 'playback',
      message: 'private story', token: 'secret', userId: 999 } as never);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/client-log');
    expect(init).toMatchObject({ method: 'POST', credentials: 'include', keepalive: true });
    expect(JSON.parse(init.body)).toEqual({ error_code: 'audio_play_failed', phase: 'playback', job_id: 31, game_id: 5, operation_id: 'voice:31' });
    expect(init.headers['X-Operation-ID']).toBe('voice:31');
  });
  it('deduplicates repeated events but keeps different jobs and handles upload failure', () => {
    const fetchMock = jest.fn().mockRejectedValue(new Error('offline'));
    global.fetch = fetchMock;
    reportDiagnostic('audio_poll_failed', { jobId: 40 });
    reportDiagnostic('audio_poll_failed', { jobId: 40 });
    reportDiagnostic('audio_poll_failed', { jobId: 41 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

it('drops values rejected by the server while preserving recovery outcome', () => {
  const fetchMock = jest.fn().mockResolvedValue({ ok: true });
  global.fetch = fetchMock;
  reportDiagnostic('voice_poll_recovered', { phase: 'x'.repeat(65), gameId: 0, jobId: 81, httpStatus: 0, attempt: 10001, outcome: 'recovered' } as never);
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ error_code: 'voice_poll_recovered', job_id: 81, outcome: 'recovered' });
});
