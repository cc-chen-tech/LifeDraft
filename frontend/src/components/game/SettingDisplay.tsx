"use client";

import { memo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  Calendar,
  User,
  Globe,
  Home,
  Users,
  Sparkles,
  Coins,
} from "lucide-react";

interface SettingDisplayProps {
  stepKey: string;
  data: Record<string, unknown>;
  isNew?: boolean; // Highlight as newly generated
  className?: string;
}

/**
 * SettingDisplay — 将各设定类型的 JSON 数据渲染为人类可读的卡片
 * 根据 stepKey 使用不同的渲染模板
 */
export const SettingDisplay = memo(function SettingDisplay({
  stepKey,
  data,
  isNew = false,
  className,
}: SettingDisplayProps) {
  return (
    <Card
      className={cn(
        "p-5 bg-card",
        isNew ? "border-primary/30 border" : "border-border",
        className
      )}
    >
      {isNew && (
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-primary" />
          <span className="text-xs text-primary font-medium">AI 生成</span>
        </div>
      )}
      {renderContent(stepKey, data)}
    </Card>
  );
});

SettingDisplay.displayName = 'SettingDisplay';

function renderContent(
  stepKey: string,
  data: Record<string, unknown>,
) {
  switch (stepKey) {
    case "era":
      return <EraDisplay data={data} />;
    case "age":
      return <AgeDisplay data={data} />;
    case "gender":
      return <GenderDisplay data={data} />;
    case "world":
      return <WorldDisplay data={data} />;
    case "family":
      return <FamilyDisplay data={data} />;
    case "relationships":
      return <RelationshipsDisplay data={data} />;
    case "traits":
      return <TraitsDisplay data={data} />;
    case "wealth":
      return <WealthDisplay data={data} />;
    default:
      // Fallback: formatted JSON
      return (
        <pre className="text-sm text-foreground whitespace-pre-wrap font-sans">
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
}

function str(val: unknown): string {
  return val != null ? String(val) : "";
}

/** Check if a key exists and has a truthy value */
function has(data: Record<string, unknown>, key: string): boolean {
  return data[key] != null && data[key] !== "";
}

// ===== Era =====
function EraDisplay({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Calendar className="w-5 h-5 text-primary flex-shrink-0" />
        <span className="text-2xl font-bold text-foreground">
          {str(data.year)}年
        </span>
      </div>
      {has(data, "era_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.era_description)}
        </p>
      )}
      {has(data, "world_context") && (
        <p className="text-sm text-muted-foreground leading-relaxed">
          {str(data.world_context)}
        </p>
      )}
    </div>
  );
}

// ===== Age =====
function AgeDisplay({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <User className="w-5 h-5 text-primary flex-shrink-0" />
        <div>
          <span className="text-2xl font-bold text-foreground">
            {str(data.age)}岁
          </span>
          {has(data, "birth_year") && (
            <span className="text-sm text-muted-foreground ml-2">
              (出生于{str(data.birth_year)}年)
            </span>
          )}
        </div>
      </div>
      {has(data, "age_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.age_description)}
        </p>
      )}
    </div>
  );
}

// ===== Gender =====
function GenderDisplay({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <User className="w-5 h-5 text-primary flex-shrink-0" />
        <span className="text-2xl font-bold text-foreground">
          {str(data.gender)}
        </span>
      </div>
      {has(data, "gender_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.gender_description)}
        </p>
      )}
    </div>
  );
}

// ===== World =====
function WorldDisplay({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Globe className="w-5 h-5 text-primary flex-shrink-0" />
        <span className="font-medium text-foreground">世界与社会</span>
      </div>
      {has(data, "world_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.world_description)}
        </p>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
        {has(data, "technology_level") && (
          <div className="bg-secondary rounded-lg p-3">
            <p className="text-xs text-muted-foreground mb-1">科技水平</p>
            <p className="text-sm text-foreground">{str(data.technology_level)}</p>
          </div>
        )}
        {has(data, "social_system") && (
          <div className="bg-secondary rounded-lg p-3">
            <p className="text-xs text-muted-foreground mb-1">社会制度</p>
            <p className="text-sm text-foreground">{str(data.social_system)}</p>
          </div>
        )}
        {has(data, "economy") && (
          <div className="bg-secondary rounded-lg p-3">
            <p className="text-xs text-muted-foreground mb-1">经济状况</p>
            <p className="text-sm text-foreground">{str(data.economy)}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ===== Family =====
function FamilyDisplay({ data }: { data: Record<string, unknown> }) {
  const members = (data.family_members || []) as (
    | string
    | { name?: string; role?: string; personality?: string }
  )[];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Home className="w-5 h-5 text-primary flex-shrink-0" />
        <span className="font-medium text-foreground">家庭背景</span>
      </div>
      {has(data, "family_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.family_description)}
        </p>
      )}
      {members.length > 0 && (
        <>
          <Separator className="my-2" />
          <div className="space-y-2">
            {members.map((member, i) => {
              if (typeof member === "string") {
                return (
                  <Badge key={i} variant="secondary" className="mr-1">
                    {member}
                  </Badge>
                );
              }
              return (
                <div key={i} className="bg-secondary rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">
                      {member.name || "未知"}
                    </span>
                    {member.role && (
                      <Badge variant="outline" className="text-xs">
                        {member.role}
                      </Badge>
                    )}
                  </div>
                  {member.personality && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {member.personality}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
      {has(data, "family_economy") && (
        <p className="text-xs text-muted-foreground">
          家庭经济: {str(data.family_economy)}
        </p>
      )}
    </div>
  );
}

// ===== Relationships =====
function RelationshipsDisplay({ data }: { data: Record<string, unknown> }) {
  const people = (data.key_people || []) as {
    name?: string;
    role?: string;
    relationship?: string;
  }[];

  // Single person result (from generate_single_relationship_person)
  if (has(data, "name") && has(data, "role")) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <Users className="w-5 h-5 text-primary flex-shrink-0" />
          <span className="font-medium text-foreground">关键人物</span>
        </div>
        <div className="bg-secondary rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-foreground">
              {str(data.name)}
            </span>
            <Badge variant="outline" className="text-xs">
              {str(data.role)}
            </Badge>
          </div>
          {has(data, "relationship") && (
            <p className="text-sm text-muted-foreground">
              {str(data.relationship)}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Users className="w-5 h-5 text-primary flex-shrink-0" />
        <span className="font-medium text-foreground">社会关系</span>
      </div>
      {has(data, "relationships_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.relationships_description)}
        </p>
      )}
      {people.length > 0 && (
        <div className="space-y-2">
          {people.map((person, i) => (
            <div key={i} className="bg-secondary rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-foreground">
                  {person.name || "未知"}
                </span>
                {person.role && (
                  <Badge variant="outline" className="text-xs">
                    {person.role}
                  </Badge>
                )}
              </div>
              {person.relationship && (
                <p className="text-xs text-muted-foreground">
                  {person.relationship}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ===== Traits =====
function TraitsDisplay({ data }: { data: Record<string, unknown> }) {
  const traits = [
    { key: "personality", label: "性格" },
    { key: "abilities", label: "能力" },
    { key: "interests", label: "兴趣" },
    { key: "strengths", label: "优点" },
    { key: "weaknesses", label: "缺点" },
  ].filter(({ key }) => has(data, key));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="w-5 h-5 text-primary flex-shrink-0" />
        <span className="font-medium text-foreground">个人特点</span>
      </div>
      {has(data, "traits_description") && (
        <p className="text-sm text-foreground leading-relaxed">
          {str(data.traits_description)}
        </p>
      )}
      {traits.length > 0 && (
        <div aria-label="角色特质" className="space-y-2" role="list">
          {traits.map(({ key, label }) => (
            <div
              className="w-full min-w-0 rounded-lg bg-secondary px-3 py-2 text-sm leading-relaxed whitespace-normal break-words"
              key={key}
              role="listitem"
            >
              <span className="font-medium text-foreground">{label}: </span>
              <span className="text-secondary-foreground">{str(data[key])}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ===== Wealth =====
function WealthDisplay({ data }: { data: Record<string, unknown> }) {
  const wealth = data.wealth as number | undefined;
  const currency = str(data.currency) || "碳信用";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Coins className="w-5 h-5 text-warning flex-shrink-0" />
        <span className="font-medium text-foreground">初始财富</span>
      </div>
      {wealth !== undefined && (
        <div className="text-2xl font-bold text-warning">
          {currency}
          {wealth.toLocaleString()}
        </div>
      )}
      {has(data, "wealth_description") && (
        <p className="text-sm text-muted-foreground leading-relaxed">
          {str(data.wealth_description)}
        </p>
      )}
    </div>
  );
}
