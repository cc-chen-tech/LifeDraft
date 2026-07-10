import React from 'react';
import { render, screen } from '@testing-library/react';
import { RoundHistoryDrawer } from '@/components/game/RoundHistoryDrawer';
import { CharacterDetail } from '@/components/game/collection/CharacterDetail';
import type { CharacterCollectionItem } from '@/lib/types';

const character: CharacterCollectionItem = {
  name: '陈远',
  role: '前同事',
  description: '仍在原公司工作的产品经理。',
  affinity: 30,
  age: 31,
  gender: '男',
  occupation: '产品经理',
  personality_traits: ['谨慎'],
  image_url: null,
  image_generated: false,
  description_generated: true,
};

describe('accessible control names', () => {
  it('gives every recorded history round a unique reading action name', () => {
    render(
      <RoundHistoryDrawer
        open
        onOpenChange={() => undefined}
        roundHistory={[
          { week: 0, round: 0, event_description: '第一周周一正文' },
          { week: 0, round: 1, story_continuation: '第一周周中正文' },
          { week: 1, round: 0, event_description: '第二周周一正文' },
        ]}
        selectedIndex={null}
        onSelect={() => undefined}
        onBackToCurrent={() => undefined}
        isViewingHistory={false}
      />,
    );

    expect(screen.getByRole('button', { name: '第 1 周 周一：阅读正文' })).toBeVisible();
    expect(screen.getByRole('button', { name: '第 1 周 周中：阅读正文' })).toBeVisible();
    expect(screen.getByRole('button', { name: '第 2 周 周一：阅读正文' })).toBeVisible();
  });

  it('names character detail close and delete controls with the character identity', () => {
    render(
      <CharacterDetail
        character={character}
        onClose={() => undefined}
        onGenerateImage={async () => undefined}
        onStartRegenerate={() => undefined}
        onCancelRegenerate={() => undefined}
        onSubmitRegenerate={async () => undefined}
        onOpenDeleteConfirm={() => undefined}
        generatingImageFor={null}
        regeneratingImageFor={null}
        showRegenerateInput={false}
        regenerateType={null}
        regenerateFeedback=""
        onRegenerateFeedbackChange={() => undefined}
        isDeleting={false}
      />,
    );

    expect(screen.getByRole('button', { name: '关闭陈远人物详情' })).toBeVisible();
    expect(screen.getByRole('button', { name: '删除人物陈远' })).toBeVisible();
  });
});
