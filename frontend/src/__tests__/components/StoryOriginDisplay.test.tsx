import { render, screen } from '@testing-library/react';

import { SettingDisplay } from '@/components/game/SettingDisplay';
import { StepPlayerInfo } from '@/components/create/StepPlayerInfo';


describe('unified story origin presentation', () => {
  it('shows the atomic date, age, era, life stage, and context without birth year', () => {
    render(
      <SettingDisplay
        stepKey="story_origin"
        data={{
          revision: 2,
          start_date: '2026-08-13',
          starting_age: 28,
          era_description: '2020年代中期的现代都市',
          life_stage_description: '职业发展逐渐进入稳定探索期',
          world_context: 'AI工具与数字内容行业快速变化',
        }}
      />,
    );

    expect(screen.getByText('2026年8月13日')).toBeInTheDocument();
    expect(screen.getByText('28岁')).toBeInTheDocument();
    expect(screen.getByText('2020年代中期的现代都市')).toBeInTheDocument();
    expect(screen.queryByText(/出生/)).not.toBeInTheDocument();
  });

  it('does not expose an independent date editor alongside identity fields', () => {
    render(
      <StepPlayerInfo
        playerName="阿衡"
        lifeVision="建立长久事业"
        onPlayerNameChange={() => undefined}
        onLifeVisionChange={() => undefined}
      />,
    );

    expect(screen.queryByLabelText(/故事开始日期/)).not.toBeInTheDocument();
    expect(document.querySelector('input[type="date"]')).toBeNull();
  });
});
