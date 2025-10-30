import React, { Component, createRef } from "react";
import { withAuthenticator } from "@aws-amplify/ui-react";
import "@aws-amplify/ui-react/styles.css";
import { Icon, Link } from "@cloudscape-design/components";
import FrameVideoMain from "./components/frameSample/videoMain";
import ClipVideoMain from "./components/videoClip/videoMain";
import NovaMmeVideoMain from "./components/novaMme/videoMain";
import TlabsMmeVideoMain from "./components/tlabsMme/videoMain";
import AgentMain from "./components/agent/agentMain";
import "./App.css";
import { FetchPost } from "./resources/data-provider";

const ITEMS = [
  { type: "link", text: "Frame Based", id: "frame", href: "#/frame" },
  { type: "link", text: "Shot Based", id: "clip", href: "#/clip" },
  { type: "link", text: "Nova MME", id: "novamme", href: "#/novamme" },
  { type: "link", text: "TwelveLabs", id: "tlabsmme", href: "#/tlabsmme" },
  { type: "link", text: "Chat with an agent", id: "agent", href: "#/agent" },
];

class App extends Component {
  constructor(props) {
    super(props);

    this.state = {
      currentPage: "frame",
      navigationOpen: true,
      activeNavHref: "#/frame",
      displayTopMenu: window.self === window.top,
      cleanSelectionSignal: null,
      smUrl: null,
    };

    this.appLayout = createRef();
    this.getReadOnlyUsers = this.getReadOnlyUsers.bind(this);
    this.handleMenuClick = this.handleMenuClick.bind(this);
    this.handleAnalyzeVideos = this.handleAnalyzeVideos.bind(this);

    const envMenus = process.env.REACT_APP_READONLY_DISPLAY_MENUS
      ? process.env.REACT_APP_READONLY_DISPLAY_MENUS.split(",")
      : [];
    this.displayMenus = envMenus;
  }

  componentDidMount() {
    this.fetchSmUrl();
  }

  async fetchSmUrl() {
    try {
      const data = await FetchPost("/extraction/video/get-sm-url", {}, "ExtrService");
      const resp = data.body;
      if (data.statusCode !== 200) {
        this.setState({ smUrl: "" });
        return "";
      } else {
        const url = resp ? resp : "";
        this.setState({ smUrl: url });
        return url;
      }
    } catch (err) {
      this.setState({ smUrl: "" });
      return "";
    }
  }

  async handleAnalyzeVideos() {
    const url = await this.fetchSmUrl();
    if (url && url.length > 0) {
      window.open(url, "_blank");
    } else {
      alert("Unable to retrieve the Studio URL. Please try again later.");
    }
  }

  getReadOnlyUsers() {
    if (process.env.REACT_APP_READONLY_USERS)
      return process.env.REACT_APP_READONLY_USERS.toString().split(",");
    else return [];
  }

  handleMenuClick(id) {
    this.setState({
      currentPage: id,
      cleanSelectionSignal: Math.random(),
    });
  }

  render() {
    const { signOut, user } = this.props;
    const { currentPage, displayTopMenu, smUrl, cleanSelectionSignal } = this.state;

    return (
      <div className="app">
        {displayTopMenu && (
          <div className="topmenu">
            <div className="title">Bedrock Video Understanding</div>
            <div className="user" title={user.email}>
              <Icon name="user-profile-active"></Icon>&nbsp;&nbsp;
              {user.username}
            </div>
          </div>
        )}

        <div className="sidemenu">
          {ITEMS.map((item, index) =>
            this.displayMenus.length === 0 || this.displayMenus.includes(item.id) ? (
              <div
                key={`menu_${index}`}
                className={item.id === currentPage ? "itemselected" : "item"}
                onClick={() => this.handleMenuClick(item.id)}
              >
                {item.text}
              </div>
            ) : (
              <div key={`empty_${index}`} />
            )
          )}

          <div className="bottom">
            <div className="item" onClick={this.handleAnalyzeVideos}>
              <Link variant="primary">Analyze Videos</Link>
              <br />
            </div>
            <div className="item" onClick={() => signOut()}>
              Logout
            </div>
          </div>
        </div>

        <div className="content">
          {currentPage === "frame" ? (
            <FrameVideoMain
              cleanSelectionSignal={cleanSelectionSignal}
              readOnlyUsers={this.getReadOnlyUsers()}
            />
          ) : currentPage === "clip" ? (
            <ClipVideoMain
              cleanSelectionSignal={cleanSelectionSignal}
              readOnlyUsers={this.getReadOnlyUsers()}
            />
          ) : currentPage === "novamme" ? (
            <NovaMmeVideoMain
              cleanSelectionSignal={cleanSelectionSignal}
              readOnlyUsers={this.getReadOnlyUsers()}
            />
          ) : currentPage === "tlabsmme" ? (
            <TlabsMmeVideoMain
              cleanSelectionSignal={cleanSelectionSignal}
              readOnlyUsers={this.getReadOnlyUsers()}
            />
          ) : currentPage === "agent" ? (
            <AgentMain
              cleanSelectionSignal={cleanSelectionSignal}
              readOnlyUsers={this.getReadOnlyUsers()}
            />
          ) : (
            <div />
          )}
        </div>
      </div>
    );
  }
}

export default withAuthenticator(App);
