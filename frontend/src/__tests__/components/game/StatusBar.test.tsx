import { render, screen } from '@testing-library/react';
import { StatusBar } from '@/components/game/StatusBar';

describe('StatusBar', () => {
  it('formats wealth with the configured currency symbol before the amount', () => {
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

    expect(screen.getByText('财富: ¥50,000')).toBeInTheDocument();
    expect(screen.queryByText('财富: 50,000人民币')).not.toBeInTheDocument();
  });
});
