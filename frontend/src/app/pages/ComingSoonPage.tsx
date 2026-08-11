import type { ReactElement } from "react";
import type { ModuleManifest } from "../../core/types/moduleManifest";
import { ModulePageLayout } from "../../design-system/layouts/ModulePageLayout";
import { EmptyState } from "../../design-system/components/EmptyState";

/** Trang hiển thị cho module status === "coming-soon". */
export function ComingSoonPage({ module }: { module: ModuleManifest }): ReactElement {
  return (
    <ModulePageLayout
      title={module.name}
      description={module.description ?? `Module ${module.name} đang được phát triển.`}
    >
      <EmptyState
        title="Module đang phát triển"
        description="Giao diện và logic quét của module này sẽ được cập nhật trong một bản phát hành sắp tới."
      />
    </ModulePageLayout>
  );
}