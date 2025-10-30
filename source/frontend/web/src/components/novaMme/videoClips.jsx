import React from 'react';
import './videoClips.css'
import { FetchPost } from "../../resources/data-provider";
import { Pagination, Spinner, ExpandableSection } from '@cloudscape-design/components';
import { DecimalToTimestamp } from "../../resources/utility";

class VideoClips extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: null, // null, loading, loaded
            alert: null,
            pageSize: 10,
            currentPageIndex: 1,
            items: null
        };
        this.item = null;
    }

    componentDidMount() {
        if (this.props.item.Request.TaskId !== null) {
          this.populateItems();    
        }
    }

    populateItems(fromIndex=null) {
        this.setState({status: "loading"});
        if (fromIndex === null)
            fromIndex = this.state.currentPageIndex
        
          FetchPost("/nova/embedding/get-task-clips", {
              "PageSize": this.state.pageSize,
              "FromIndex": (fromIndex - 1) * this.state.pageSize,
              "TaskId": this.props.item.Request.TaskId,
          }, "NovaService").then((data) => {
                  var resp = data.body;
                  if (data.statusCode !== 200) {
                      this.setState( {status: null, alert: data.body});
                  }
                  else {
                      if (resp !== null) {
                          //console.log(items);
                          this.setState(
                              {
                                  items: resp,
                                  status: null,
                                  alert: null,
                              }
                          );
                      }
                  }
              })
              .catch((err) => {
                  this.setState( {status: null, alert: err.message});
              });              
    }

    handleClipClick(timestamp) {
        //alert(timestamp);
        this.props.OnClipClick(timestamp);
    }

    render() {
        return (
            <div className="videoclips">
                {this.state.items && Object.entries(this.state.items).map(([embedOption, clips]) => (
                    <ExpandableSection headerText={`${embedOption} (${clips.length})`}>
                        {clips.map((item, index) => (
                            <div className='clip' onClick={()=>this.handleClipClick(item.StartSec)}>{item.StartSec.toFixed(2)} - {item.EndSec.toFixed(2)}</div>
                        ))}
                    </ExpandableSection>
                ))}
                {this.state.status === "loading"?<Spinner/>:<div/>}
            </div>
        );
    }
}

export default VideoClips;