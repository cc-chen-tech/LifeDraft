import { render, screen } from '@testing-library/react';
import { StatusBar } from '@/components/game/StatusBar';

describe('StatusBar', () => {
  it('hides wealth even when a configured currency symbol is available', () => {
    render(
      <StatusBar
        playerState={{
          age: 22,
          week: 0,
          energy: 80,
          mood: 70,
          knowledge: 20,
          wealth: 50000,
          character_settings: {
            wealth: {
              currency: '¥',
              currency_name: '人民币',
            },
          },
        }}
        progress={{ current_round: 1, total_rounds: 3 }}
        compact
      />,
    );

    expect(screen.getByText('22岁 第1周')).toBeInTheDocument();
    expect(screen.getByText('1/3')).toBeInTheDocument();
    expect(screen.queryByText('财富: ¥50,000')).not.toBeInTheDocument();
    expect(screen.queryByText('财富: 50,000人民币')).not.toBeInTheDocument();
    expect(screen.queryByText(/精力|情绪|学识|财富/)).not.toBeInTheDocument();
  });
});
