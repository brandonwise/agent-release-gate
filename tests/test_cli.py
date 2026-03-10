from agent_release_gate.cli import build_parser


def test_parser_has_evaluate_command():
    parser = build_parser()
    args = parser.parse_args(["evaluate", "--spec", "a.yaml", "--results", "b.json"])
    assert args.command == "evaluate"
    assert args.spec == "a.yaml"
    assert args.results == "b.json"
