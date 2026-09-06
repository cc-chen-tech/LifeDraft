import { fireEvent, render, screen, within } from "@testing-library/react";

import { VoicePicker } from "@/components/game/VoicePicker";
import type { MiniMaxVoiceOption } from "@/lib/types";

const voices: MiniMaxVoiceOption[] = [
  {
    voice_id: "female-shaonv",
    label: "少女音色",
    language: "普通话",
    group: "标准音色",
    recommended: true,
  },
  {
    voice_id: "Chinese (Mandarin)_Gentleman",
    label: "温润男声",
    language: "普通话",
    group: "主播与叙事",
    recommended: false,
  },
];

describe("VoicePicker", () => {
  it("separates catalog selection from preview and closes with Escape", () => {
    const onSelectVoice = jest.fn();
    const onPreviewVoice = jest.fn();

    render(
      <VoicePicker
        voices={voices}
        selectedVoiceId="female-shaonv"
        previewingVoice={null}
        onSelectVoice={onSelectVoice}
        onPreviewVoice={onPreviewVoice}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "查看全部中文音色" }));
    const dialog = screen.getByRole("dialog", { name: "全部中文音色" });

    fireEvent.click(within(dialog).getByRole("button", { name: "试听温润男声" }));
    expect(onPreviewVoice).toHaveBeenCalledWith("Chinese (Mandarin)_Gentleman");

    fireEvent.click(within(dialog).getByRole("button", { name: "选择温润男声" }));
    expect(onSelectVoice).toHaveBeenCalledWith("Chinese (Mandarin)_Gentleman");
    expect(screen.queryByRole("dialog", { name: "全部中文音色" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看全部中文音色" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "全部中文音色" })).not.toBeInTheDocument();
  });
});
