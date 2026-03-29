import { http, HttpResponse } from 'msw';

export const handlers = [
  // Mock 音乐推荐 API
  http.post('http://localhost:8000/api/music/recommend', async ({ request }) => {
    const body = await request.json() as { story_text: string };
    
    // 根据请求返回不同的响应
    if (body.story_text === 'no-url-story') {
      return HttpResponse.json({
        songs: [
          { id: 1, name: 'Song 1', artist: 'Artist 1', artists: ['Artist 1'], album: 'Album 1' },
        ],
        keywords: ['test'],
        description: 'Test description',
      });
    }
    
    // 默认返回包含 URL 的歌曲
    return HttpResponse.json({
      songs: [
        { id: 1, name: 'Test Song', artist: 'Test Artist', artists: ['Test Artist'], album: 'Test Album', url: 'http://example.com/song.mp3' },
      ],
      keywords: ['test'],
      description: 'Test description',
    });
  }),

  // Mock 歌曲 URL API
  http.get('http://localhost:8000/api/music/song-url', ({ request }) => {
    const url = new URL(request.url);
    const songId = url.searchParams.get('song_id');
    
    return HttpResponse.json({
      url: `http://example.com/song-${songId}.mp3`,
    });
  }),
];
