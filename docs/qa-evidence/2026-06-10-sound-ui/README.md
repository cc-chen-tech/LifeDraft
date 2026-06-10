# Sound UI Regression Evidence - 2026-06-10

Scope: verify the global sound UI presents music and story reading as one sound panel.

## Browser Fixtures

- URL: `http://localhost:3147/e2e-regression?globalVoice=1`
- Desktop viewport: `1440x1000`
- Mobile viewport: `390x844`

## Verified Behavior

- Collapsed global sound bar exposes one action: `展开声音`.
- Collapsed bar does not expose `播放音乐`, `暂停音乐`, or `朗读故事`.
- Expanded panel exposes one group: `音乐和朗读`.
- Expanded panel contains one music section and one reading section.
- Expanded panel contains `收起声音` and replaces the collapsed mini bar while open.
- Expanded panel keeps voice selection and auto-read controls in the reading section.
- Expanded panel does not contain a nested standalone `故事朗读` region.

## Evidence

- `desktop-expanded.png`
- `mobile-expanded.png`
