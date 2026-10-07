import { createHealerPR } from "../shared/github-client";
import { readPipelineState, writePipelineState } from "../shared/s3-client";
import { PipelineState } from "../shared/types";

export const handler = async (input: { executionId: string }): Promise<{ executionId: string }> => {
  const state = await readPipelineState<PipelineState>(input.executionId);
  try {
    const { prUrl, prNumber } = await createHealerPR(state);
    await writePipelineState({ ...state, prUrl, prNumber });
  } catch (err) {
    await writePipelineState({
      ...state,
      stageError: err instanceof Error ? err.message : String(err),
      failedStage: "PR",
    });
  }
  return input; // Pass executionId through for next stage
};
