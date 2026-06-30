function main(argv: string[]): number {
  if (argv.includes("--help") || argv.length === 0) {
    console.log("Usage: tsx src/cli.ts --spec <path> [--headed] [--prove]");
    return 0;
  }
  console.log("not implemented yet");
  return 0;
}

process.exit(main(process.argv.slice(2)));
