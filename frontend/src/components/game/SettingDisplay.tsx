"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

interface SettingDisplayProps {
  stepKey: string;
  data: Record<string, unknown>;
  isNew?: boolean; // Highlight as newly generated
  className?: string;
}

/**
 * SettingDisplay — 将各设定类型的 JSON 数据渲染为人类可读的章节
 * 根据 stepKey 使用不同的渲染模板
 */
export const SettingDisplay = memo(function SettingDisplay({
  stepKey,
  data,
  isNew = false,
  className,
}: SettingDisplayProps) {
  if (stepKey === "wealth") return null;

  return (
    <section
      data-slot="setting-display"
      data-state={isNew ? "new" : undefined}
      className={cn(
        "min-w-0 border-y border-[var(--border-default)] py-5",
        "font-serif text-[var(--text-primary)]",
        className
      )}
    >
      {isNew && (
        <p className="mb-4 text-xs font-sans text-[var(--text-secondary)]">
          刚刚生成
        </p>
      )}
      {renderContent(stepKey, data)}
    </section>
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
    default:
      // Fallback: formatted JSON
      return (
        <pre className="min-w-0 whitespace-pre-wrap break-words font-sans text-sm text-[var(--text-primary)]">
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
      <div className="min-w-0">
        <span className="break-words text-2xl font-semibold text-[var(--text-primary)]">
          {str(data.year)}年
        </span>
      </div>
      {has(data, "era_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
          {str(data.era_description)}
        </p>
      )}
      {has(data, "world_context") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-secondary)]">
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
      <div className="min-w-0">
        <div className="min-w-0">
          <span className="break-words text-2xl font-semibold text-[var(--text-primary)]">
            {str(data.age)}岁
          </span>
          {has(data, "birth_year") && (
            <span className="ml-2 break-words text-sm text-[var(--text-secondary)]">
              (出生于{str(data.birth_year)}年)
            </span>
          )}
        </div>
      </div>
      {has(data, "age_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
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
      <div className="min-w-0">
        <span className="break-words text-2xl font-semibold text-[var(--text-primary)]">
          {str(data.gender)}
        </span>
      </div>
      {has(data, "gender_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
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
      <h3 className="font-sans text-sm font-medium text-[var(--text-primary)]">世界与社会</h3>
      {has(data, "world_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
          {str(data.world_description)}
        </p>
      )}
      <div className="mt-2 grid min-w-0 grid-cols-1 border-t border-[var(--border-default)] sm:grid-cols-2">
        {has(data, "technology_level") && (
          <div className="min-w-0 border-b border-[var(--border-default)] py-3 sm:pr-4">
            <p className="mb-1 text-xs font-sans text-[var(--text-secondary)]">科技水平</p>
            <p className="break-words text-sm text-[var(--text-primary)]">{str(data.technology_level)}</p>
          </div>
        )}
        {has(data, "social_system") && (
          <div className="min-w-0 border-b border-[var(--border-default)] py-3 sm:pl-4">
            <p className="mb-1 text-xs font-sans text-[var(--text-secondary)]">社会制度</p>
            <p className="break-words text-sm text-[var(--text-primary)]">{str(data.social_system)}</p>
          </div>
        )}
        {has(data, "economy") && (
          <div className="min-w-0 border-b border-[var(--border-default)] py-3 sm:pr-4">
            <p className="mb-1 text-xs font-sans text-[var(--text-secondary)]">经济状况</p>
            <p className="break-words text-sm text-[var(--text-primary)]">{str(data.economy)}</p>
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
      <h3 className="font-sans text-sm font-medium text-[var(--text-primary)]">家庭背景</h3>
      {has(data, "family_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
          {str(data.family_description)}
        </p>
      )}
      {members.length > 0 && (
        <>
          <div className="border-t border-[var(--border-default)]">
            {members.map((member, i) => {
              if (typeof member === "string") {
                return (
                  <p key={i} className="break-words border-b border-[var(--border-default)] py-3 text-sm">
                    {member}
                  </p>
                );
              }
              return (
                <div key={i} className="min-w-0 border-b border-[var(--border-default)] py-3">
                  <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="break-words text-sm font-medium text-[var(--text-primary)]">
                      {member.name || "未知"}
                    </span>
                    {member.role && (
                      <span className="break-words text-xs font-sans text-[var(--text-secondary)]">
                        {member.role}
                      </span>
                    )}
                  </div>
                  {member.personality && (
                    <p className="mt-1 break-words text-xs leading-relaxed text-[var(--text-secondary)]">
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
        <p className="break-words text-xs text-[var(--text-secondary)]">
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
        <h3 className="font-sans text-sm font-medium text-[var(--text-primary)]">关键人物</h3>
        <div className="min-w-0 border-t border-[var(--border-default)] py-3">
          <div className="mb-1 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="break-words text-sm font-medium text-[var(--text-primary)]">
              {str(data.name)}
            </span>
            <span className="break-words text-xs font-sans text-[var(--text-secondary)]">
              {str(data.role)}
            </span>
          </div>
          {has(data, "relationship") && (
            <p className="break-words text-sm leading-relaxed text-[var(--text-secondary)]">
              {str(data.relationship)}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="font-sans text-sm font-medium text-[var(--text-primary)]">社会关系</h3>
      {has(data, "relationships_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
          {str(data.relationships_description)}
        </p>
      )}
      {people.length > 0 && (
        <div className="border-t border-[var(--border-default)]">
          {people.map((person, i) => (
            <div key={i} className="min-w-0 border-b border-[var(--border-default)] py-3">
              <div className="mb-1 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                <span className="break-words text-sm font-medium text-[var(--text-primary)]">
                  {person.name || "未知"}
                </span>
                {person.role && (
                  <span className="break-words text-xs font-sans text-[var(--text-secondary)]">
                    {person.role}
                  </span>
                )}
              </div>
              {person.relationship && (
                <p className="break-words text-xs leading-relaxed text-[var(--text-secondary)]">
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
      <h3 className="font-sans text-sm font-medium text-[var(--text-primary)]">个人特点</h3>
      {has(data, "traits_description") && (
        <p className="break-words text-sm leading-relaxed text-[var(--text-primary)]">
          {str(data.traits_description)}
        </p>
      )}
      {traits.length > 0 && (
        <div aria-label="角色特质" className="border-t border-[var(--border-default)]" role="list">
          {traits.map(({ key, label }) => (
            <div
              className="w-full min-w-0 border-b border-[var(--border-default)] py-3 text-sm leading-relaxed whitespace-normal break-words"
              key={key}
              role="listitem"
            >
              <span className="font-sans font-medium text-[var(--text-primary)]">{label}: </span>
              <span className="text-[var(--text-secondary)]">{str(data[key])}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
