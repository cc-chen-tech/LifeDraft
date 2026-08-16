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

  it('marks the recommended option without reordering or stealing focus', () => {
    render(
      <OptionCards
        options={[
          { text: '沿河追查', likely_choice: false },
          { text: '返回客栈', likely_choice: true },
          { text: '拜访旧友', likely_choice: false },
        ]}
        onSelect={() => undefined}
        allowCustomChoice={false}
      />
    );

    expect(screen.getAllByText('推荐 · 更贴近愿景')).toHaveLength(1);
    const recommended = screen.getByRole('button', {
      name: '推荐，更贴近愿景，选择 2：返回客栈',
    });
    expect(recommended).toBeVisible();
    expect(document.activeElement).not.toBe(recommended);
    expect(screen.getAllByTestId(/option-text-/).map((node) => node.textContent)).toEqual([
      '沿河追查',
      '返回客栈',
      '拜访旧友',
    ]);
  });
});
