//! `omniscroll-cli` - Fast native command-line tool for OmniScroll.

use clap::{Parser, Subcommand};
use omniscroll_bridge::SerialBridge;

#[derive(Parser)]
#[command(name = "omniscroll-cli")]
#[command(about = "OmniScroll Hardware Diagnostics & Flashing Tool", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Detects connected OmniScroll devices over USB
    Ports,
    /// Monitor live serial telemetry stream
    Monitor {
        #[arg(short, long)]
        port: Option<String>,
    },
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Ports => {
            println!("[*] Scanning for OmniScroll devices...");
            match SerialBridge::find_omniscroll_port() {
                Some(port) => println!("[+] OmniScroll detected on {}", port),
                None => println!("[-] No OmniScroll device detected (VID 0x303A / PID 0x4F5B)."),
            }
        }
        Commands::Monitor { port } => {
            let p = port.or_else(SerialBridge::find_omniscroll_port);
            match p {
                Some(port_name) => println!("[*] Monitoring OmniScroll on {}...", port_name),
                None => eprintln!("[-] No device specified or found."),
            }
        }
    }
}
