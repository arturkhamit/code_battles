export type TaskInfo = {
  id: number;
  name: string;
  description: string;
  time_limit: { seconds: number; nanos: number } | null;
  memory_limit_bytes: number | null;
  public_tests: {
    input: string[];
    output: string[];
  };
};
