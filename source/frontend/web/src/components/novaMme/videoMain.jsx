import React from 'react';
import './videoMain.css'
import { Button, Modal, Icon, Tabs } from '@cloudscape-design/components';
import VideoSearch from './videoSearch'
import VideoDetail from './videoDetail'
import { getCurrentUser } from 'aws-amplify/auth';

class NovaMmeVideoMain extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: "loading", // null, loading, loaded
            alert: null,
            items: null,
            filterText: null,
            selectedItemId: null,
            currentUserName: null,
            refreshSearchTaskId: false,
        };
    }
    async componentDidMount() {
        if (this.state.currentUserName === null) {
            const { username } = await getCurrentUser();
            this.setState({currentUserName: username});
        }
    }

    componentDidUpdate(prevProps) {
        if (prevProps.cleanSelectionSignal !== this.props.cleanSelectionSignal) {
            this.setState({selectedItemId: null})
        }
      }

    handleThumbnailClick = (taskId, autoPlay=false) => {
        this.setState({selectedItemId: taskId, autoPlay: autoPlay});
    }

    render() {
        return (
            <div className="videomain">
                {this.state.selectedItemId === null?
                <div>
                    <VideoSearch 
                            onThumbnailClick={this.handleThumbnailClick} 
                            currentUserName={this.state.currentUserName}
                            readonlyMode={this.props.readOnlyUsers.includes(this.state.currentUserName)}
                            refreshSearchTaskId={this.state.refreshSearchTaskId}
                            />
                </div>
                :<VideoDetail 
                    taskId={this.state.selectedItemId} 
                    autoPlay={this.state.autoPlay}
                    onClose={(detail)=> this.setState({selectedItemId: null})}
                >
                </VideoDetail>
                }

            </div>
        );
    }
}

export default NovaMmeVideoMain;