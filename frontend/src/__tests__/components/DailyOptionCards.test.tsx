import { render, screen } from '@testing-library/react';

import { OptionCards } from '@/components/game/OptionCards';

describe('daily option cards', () => {
  it('shows only generated options when custom choices are disabled', () => {
    render(
      <OptionCards
        options={[{ text: '沿河追查' }, { text: '返回客栈' }]}
        onSelect={() => undefined}
        allowCustomChoice={false}
      />
    );

    expect(screen.getByRole('button', { name: '选择 1：沿河追查' })).toBeVisible();
    expect(screen.queryByPlaceholderText('或者，描述你想做的事情...')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '提交自定义选择' })).not.toBeInTheDocument();
  });
});
