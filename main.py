"""
============================================================
main.py — Personal AI Memory System Entry Point
============================================================
Usage:
    python main.py                  # Run full pipeline once
    python main.py --dry-run        # Check connectivity
    python main.py --schedule       # Run daily at 3 AM
    python main.py --dashboard      # Launch Streamlit dashboard
============================================================
"""

import sys
import os
import argparse


def main():
    """Parse arguments and run the appropriate mode."""
    parser = argparse.ArgumentParser(
        description="Personal AI Memory System for WordPress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      Run the full pipeline once
  python main.py --dry-run            Check connectivity only
  python main.py --schedule           Run daily at 3:00 AM
  python main.py --dashboard          Launch the Streamlit dashboard

Setup:
  1. Copy .env.example to .env and fill in credentials
  2. pip install -r requirements.txt
  3. (Optional) Start Neo4j Community Edition locally
        """,
    )

    parser.add_argument("--dry-run", action="store_true", help="Verify connectivity")
    parser.add_argument("--schedule", action="store_true", help="Run on daily schedule")
    parser.add_argument("--hour", type=int, default=3, help="Schedule hour (default: 3)")
    parser.add_argument("--minute", type=int, default=0, help="Schedule minute (default: 0)")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit dashboard")

    args = parser.parse_args()

    if args.dashboard:
        # Launch Flask dashboard
        print("[Main] Launching Flask dashboard at http://localhost:5000...")
        os.system(f"{sys.executable} app.py")
        return

    # Import pipeline only when needed (avoids loading all deps for --dashboard)
    from pipeline import MemoryPipeline

    pipeline = MemoryPipeline()

    try:
        if args.schedule:
            pipeline.run(dry_run=True)
            pipeline.schedule_daily(hour=args.hour, minute=args.minute)
        elif args.dry_run:
            report = pipeline.run(dry_run=True)
            sys.exit(0 if report.get("success") else 1)
        else:
            report = pipeline.run()
            if report.get("success"):
                print("\n✓ Pipeline completed successfully!")
            else:
                print(f"\n✗ Failed: {report.get('error', 'Unknown')}")
                sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Main] Interrupted")
    finally:
        pipeline.cleanup()


if __name__ == "__main__":
    main()
