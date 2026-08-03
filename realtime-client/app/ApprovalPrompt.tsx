"use client";

import { Check, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const OTHER_VALUE = "__other__";

export interface ApprovalOption {
  label: string;
  value: string;
}

export interface ApprovalQuestion {
  question_id: string;
  question: string;
  options: ApprovalOption[];
  multi_select: boolean;
  allow_other: boolean;
  operation?: string;
}

export const normalizeApprovalQuestions = (value: unknown): ApprovalQuestion[] => {
  if (!Array.isArray(value)) return [];

  return value.flatMap((item, index) => {
    if (!item || typeof item !== "object") return [];
    const raw = item as Record<string, unknown>;
    const question = String(raw.question ?? "").trim();
    if (!question) return [];

    const options = Array.isArray(raw.options)
      ? raw.options.flatMap((option) => {
          if (option && typeof option === "object") {
            const data = option as Record<string, unknown>;
            const label = String(data.label ?? data.value ?? "").trim();
            const optionValue = String(data.value ?? data.label ?? "").trim();
            return label && optionValue ? [{ label, value: optionValue }] : [];
          }
          const text = String(option ?? "").trim();
          return text ? [{ label: text, value: text }] : [];
        })
      : [];

    return [
      {
        question_id: String(raw.question_id ?? `q-${index + 1}`).trim() || `q-${index + 1}`,
        question,
        options,
        multi_select: Boolean(raw.multi_select),
        allow_other: raw.allow_other !== false,
        operation: String(raw.operation ?? "").trim() || undefined,
      },
    ];
  });
};

export function ApprovalPrompt({
  questions,
  processing,
  onSubmit,
  onReject,
}: {
  questions: ApprovalQuestion[];
  processing: boolean;
  onSubmit: (answer: Record<string, unknown>) => void;
  onReject: () => void;
}) {
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [other, setOther] = useState<Record<string, string>>({});

  useEffect(() => {
    setSelected({});
    setOther({});
  }, [questions]);

  const isComplete = useMemo(
    () =>
      questions.every((question) => {
        const values = selected[question.question_id] ?? [];
        if (values.includes(OTHER_VALUE)) {
          return Boolean(other[question.question_id]?.trim());
        }
        return values.length > 0;
      }),
    [other, questions, selected],
  );

  const updateSelection = (question: ApprovalQuestion, value: string) => {
    setSelected((current) => {
      const values = current[question.question_id] ?? [];
      const next = question.multi_select
        ? values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value]
        : [value];
      return { ...current, [question.question_id]: next };
    });
  };

  const submit = () => {
    if (!isComplete || processing) return;
    const answer: Record<string, unknown> = {};
    for (const question of questions) {
      const values = selected[question.question_id] ?? [];
      if (values.includes(OTHER_VALUE)) {
        answer[question.question_id] = {
          type: "other",
          text: other[question.question_id]?.trim() ?? "",
          selected: values.filter((value) => value !== OTHER_VALUE),
        };
      } else {
        answer[question.question_id] = question.multi_select ? values : values[0];
      }
    }
    onSubmit(answer);
  };

  return (
    <section className="approval-prompt" aria-label="AI 需要你的确认">
      <header>
        <strong>需要你的回答</strong>
        <span>也可以直接说出或输入答案</span>
      </header>
      <div className="approval-questions">
        {questions.map((question, index) => {
          const values = selected[question.question_id] ?? [];
          return (
            <fieldset key={question.question_id} disabled={processing}>
              <legend>
                {questions.length > 1 ? `${index + 1}. ` : ""}
                {question.question}
              </legend>
              {question.operation && <p className="approval-operation">操作：{question.operation}</p>}
              <div className="approval-options">
                {question.options.map((option) => (
                  <label key={`${question.question_id}-${option.value}`}>
                    <input
                      type={question.multi_select ? "checkbox" : "radio"}
                      name={`approval-${question.question_id}`}
                      checked={values.includes(option.value)}
                      onChange={() => updateSelection(question, option.value)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
                {question.allow_other && (
                  <label className="approval-other-option">
                    <input
                      type={question.multi_select ? "checkbox" : "radio"}
                      name={`approval-${question.question_id}`}
                      checked={values.includes(OTHER_VALUE)}
                      onChange={() => updateSelection(question, OTHER_VALUE)}
                    />
                    <input
                      type="text"
                      value={other[question.question_id] ?? ""}
                      placeholder="其他答案"
                      onFocus={() => {
                        if (!values.includes(OTHER_VALUE)) updateSelection(question, OTHER_VALUE);
                      }}
                      onChange={(event) =>
                        setOther((current) => ({
                          ...current,
                          [question.question_id]: event.target.value,
                        }))
                      }
                    />
                  </label>
                )}
              </div>
            </fieldset>
          );
        })}
      </div>
      <footer>
        <button type="button" className="approval-reject" disabled={processing} onClick={onReject}>
          <X />
          拒绝
        </button>
        <button type="button" disabled={!isComplete || processing} onClick={submit}>
          <Check />
          {processing ? "处理中" : "提交"}
        </button>
      </footer>
    </section>
  );
}
