/**
 * SettingDisplay Component Tests
 * Tests for the setting display component
 */
import { render, screen } from '@testing-library/react';
import { SettingDisplay } from '@/components/game/SettingDisplay';

describe('SettingDisplay', () => {
  describe('rendering', () => {
    it('renders era setting correctly', () => {
      const eraData = {
        year: 2020,
        era_description: '信息时代',
      };

      render(<SettingDisplay stepKey="era" data={eraData} />);

      expect(screen.getByText(/2020/)).toBeInTheDocument();
      expect(screen.getByText('信息时代')).toBeInTheDocument();
    });

    it('renders age setting correctly', () => {
      const ageData = {
        age: 25,
        age_range: '青年',
      };

      render(<SettingDisplay stepKey="age" data={ageData} />);

      expect(screen.getByText(/25/)).toBeInTheDocument();
    });

    it('renders gender setting correctly', () => {
      const genderData = {
        gender: '男',
      };

      render(<SettingDisplay stepKey="gender" data={genderData} />);

      expect(screen.getByText('男')).toBeInTheDocument();
    });

    it('renders world setting correctly', () => {
      const worldData = {
        world_description: '现代都市世界',
        technology_level: '高科技',
      };

      render(<SettingDisplay stepKey="world" data={worldData} />);

      expect(screen.getByText('现代都市世界')).toBeInTheDocument();
      expect(screen.getByText('高科技')).toBeInTheDocument();
    });

    it('renders family setting correctly', () => {
      const familyData = {
        family_background: '普通家庭',
        parents: ['父亲', '母亲'],
      };

      render(<SettingDisplay stepKey="family" data={familyData} />);

      // Should render family content
      expect(screen.getByText(/家庭|父母|父母职业/i)).toBeInTheDocument();
    });

    it('renders relationships setting correctly', () => {
      const relationshipsData = {
        relationships: [
          { name: '张三', relationship: '朋友' },
        ],
      };

      render(<SettingDisplay stepKey="relationships" data={relationshipsData} />);

      // Should render relationships content
      expect(screen.getByText(/张三|朋友|关系/i)).toBeInTheDocument();
    });

    it('renders traits setting correctly', () => {
      const traitsData = {
        personality: ['乐观', '坚韧'],
        skills: ['编程'],
      };

      render(<SettingDisplay stepKey="traits" data={traitsData} />);

      // Should render traits content
      expect(screen.getByText(/乐观|坚韧|性格/i)).toBeInTheDocument();
    });

    it('renders wealth setting correctly', () => {
      const wealthData = {
        wealth_level: '中等',
        assets: '一套房产',
      };

      render(<SettingDisplay stepKey="wealth" data={wealthData} />);

      // Should render wealth content
      expect(screen.getByText(/中等|财富|资产/i)).toBeInTheDocument();
    });
  });

  describe('fallback rendering', () => {
    it('renders JSON for unknown stepKey', () => {
      const unknownData = {
        custom_field: 'custom value',
      };

      render(<SettingDisplay stepKey="unknown" data={unknownData} />);

      expect(screen.getByText(/custom_field/)).toBeInTheDocument();
      expect(screen.getByText(/custom value/)).toBeInTheDocument();
    });
  });

  describe('isNew prop', () => {
    it('shows AI generated badge when isNew is true', () => {
      const data = { test: 'value' };

      render(<SettingDisplay stepKey="unknown" data={data} isNew={true} />);

      expect(screen.getByText(/AI 生成/)).toBeInTheDocument();
    });

    it('does not show badge when isNew is false', () => {
      const data = { test: 'value' };

      render(<SettingDisplay stepKey="unknown" data={data} isNew={false} />);

      expect(screen.queryByText(/AI 生成/)).not.toBeInTheDocument();
    });

    it('does not show badge when isNew is not provided', () => {
      const data = { test: 'value' };

      render(<SettingDisplay stepKey="unknown" data={data} />);

      expect(screen.queryByText(/AI 生成/)).not.toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className', () => {
      const data = { test: 'value' };

      const { container } = render(
        <SettingDisplay stepKey="unknown" data={data} className="custom-class" />
      );

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('edge cases', () => {
    it('handles empty data object', () => {
      const { container } = render(<SettingDisplay stepKey="era" data={{}} />);

      // Should render without crashing
      expect(container.firstChild).toBeInTheDocument();
    });

    it('handles null values in data', () => {
      const dataWithNull = {
        era_name: null,
        era_description: 'test',
      };

      const { container } = render(<SettingDisplay stepKey="era" data={dataWithNull} />);

      // Should render without crashing
      expect(container.firstChild).toBeInTheDocument();
    });

    it('handles undefined values in data', () => {
      const dataWithUndefined = {
        era_name: undefined,
        era_description: 'test',
      };

      const { container } = render(<SettingDisplay stepKey="era" data={dataWithUndefined} />);

      // Should render without crashing
      expect(container.firstChild).toBeInTheDocument();
    });
  });
});
